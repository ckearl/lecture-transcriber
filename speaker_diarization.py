import os
import json
import logging
import asyncio
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

# Handle numpy compatibility
try:
    import numpy as np
    # Handle np.NaN vs np.nan compatibility
    if not hasattr(np, 'NaN'):
        np.NaN = np.nan
except ImportError as e:
    logging.error(f"Failed to import numpy: {e}")
    raise

# Handle torchaudio backend warnings
import warnings
warnings.filterwarnings(
    "ignore", message=".*torchaudio._backend.set_audio_backend.*")
warnings.filterwarnings(
    "ignore", message=".*torchaudio._backend.set_audio_backend has been deprecated.*")

# pyannote.audio imports with error handling
try:
    import torch
    import torchaudio

    # Suppress torchaudio backend warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from pyannote.audio import Pipeline
        from pyannote.core import Annotation, Segment

except ImportError as e:
    logging.error(f"Failed to import required audio libraries: {e}")
    logging.error(
        "Please ensure you have installed: torch, torchaudio, pyannote.audio")
    raise Exception(f"Missing required dependencies: {e}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """
    Speaker diarization using pyannote.audio (Hugging Face).
    
    Handles speaker identification for MBA lecture recordings, typically
    involving 1-3 speakers (professor + students).
    """

    def __init__(self):
        """Initialize speaker diarization pipeline."""
        self.pipeline = None
        self.status_tracker: Dict[str, str] = {}
        self.results_tracker: Dict[str, Dict] = {}
        self.transcriptions_dir = Path("transcriptions")

        # Initialize pyannote.audio pipeline
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Initialize the pyannote.audio speaker diarization pipeline."""
        try:
            # Get Hugging Face token from environment
            hf_token = os.getenv('HUGGINGFACE_API_KEY')
            if not hf_token:
                logger.error(
                    "HUGGINGFACE_API_KEY environment variable not set")
                raise ValueError(
                    "HUGGINGFACE_API_KEY environment variable is required")

            # Load pre-trained pipeline - using the recommended model
            logger.info(
                "Loading pyannote.audio speaker diarization pipeline...")
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )

            # Set device (GPU if available, CPU otherwise)
            device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu")
            self.pipeline = self.pipeline.to(device)

            logger.info(
                f"Speaker diarization pipeline loaded successfully on {device}")

        except Exception as e:
            logger.error(f"Failed to initialize pyannote.audio pipeline: {e}")
            self.pipeline = None
            raise Exception(f"Pipeline initialization failed: {str(e)}")

    def get_diarization_status(self, transcription_uuid: str) -> str:
        """Get the current status of speaker diarization."""
        return self.status_tracker.get(transcription_uuid, "not_started")

    def get_diarization_results(self, transcription_uuid: str) -> Optional[Dict]:
        """Get the speaker diarization results."""
        return self.results_tracker.get(transcription_uuid, None)

    def update_status(self, transcription_uuid: str, status: str):
        """Update diarization status."""
        self.status_tracker[transcription_uuid] = status
        logger.info(
            f"Diarization status updated for {transcription_uuid}: {status}")

    def load_transcription_json(self, transcription_uuid: str) -> Tuple[Optional[Dict], Optional[Path]]:
        """Load existing transcription JSON by UUID."""
        try:
            # Search through all class directories
            for class_dir in self.transcriptions_dir.iterdir():
                if class_dir.is_dir():
                    for json_file in class_dir.glob("*.json"):
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            if data.get("transcription_uuid") == transcription_uuid:
                                logger.info(
                                    f"Found transcription JSON: {json_file}")
                                return data, json_file
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(
                                f"Skipping malformed JSON file {json_file}: {e}")
                            continue

            logger.warning(
                f"Transcription not found for UUID: {transcription_uuid}")
            return None, None

        except Exception as e:
            logger.error(f"Failed to load transcription: {e}")
            return None, None

    def save_updated_transcription(self, transcription_data: Dict, file_path: Path):
        """Save updated transcription with speaker information."""
        try:
            # Ensure the directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Add processing timestamp
            transcription_data["diarization_processed"] = datetime.now(
            ).isoformat()

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated transcription saved: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save updated transcription: {e}")
            raise

    def preprocess_audio(self, audio_path: Path) -> Path:
        """
        Preprocess audio file for optimal diarization.
        Convert to appropriate format and sample rate if needed.
        """
        try:
            logger.info(f"Preprocessing audio file: {audio_path}")

            # Load audio
            waveform, sample_rate = torchaudio.load(str(audio_path))

            # Convert to mono if stereo
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
                logger.info("Converted stereo to mono")

            # Resample to 16kHz if needed (optimal for speech processing)
            target_sample_rate = 16000
            if sample_rate != target_sample_rate:
                resampler = torchaudio.transforms.Resample(
                    sample_rate, target_sample_rate)
                waveform = resampler(waveform)
                logger.info(
                    f"Resampled from {sample_rate}Hz to {target_sample_rate}Hz")

            # Save preprocessed audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                preprocessed_path = Path(tmp_file.name)

            torchaudio.save(str(preprocessed_path),
                            waveform, target_sample_rate)
            logger.info(f"Preprocessed audio saved: {preprocessed_path}")

            return preprocessed_path

        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            # Return original path if preprocessing fails
            return audio_path

    def process_diarization_results(
        self,
        diarization_output: Annotation,
        transcription_timestamps: List[Dict]
    ) -> List[Dict]:
        """
        Process pyannote.audio diarization output and map to transcription timestamps.
        
        Args:
            diarization_output: Annotation object from pyannote.audio
            transcription_timestamps: List of timestamp segments from Whisper
            
        Returns:
            List[Dict]: List of speaker objects with timestamps
        """
        try:
            logger.info("Processing diarization results...")

            # Extract speaker segments from annotation
            speaker_segments = {}
            for segment, _, speaker in diarization_output.itertracks(yield_label=True):
                if speaker not in speaker_segments:
                    speaker_segments[speaker] = []
                speaker_segments[speaker].append({
                    'start': segment.start,
                    'end': segment.end
                })

            logger.info(f"Detected {len(speaker_segments)} speakers")

            # Create speaker objects
            speakers = []
            speaker_names = sorted(speaker_segments.keys())

            for i, speaker_id in enumerate(speaker_names):
                speaker_name = f"Speaker {i + 1}"
                segments = speaker_segments[speaker_id]

                # Map speaker segments to transcription text
                speaker_timestamps = []
                for segment in segments:
                    # Find overlapping transcription segments
                    for trans_segment in transcription_timestamps:
                        trans_start = trans_segment.get('start', 0)
                        trans_end = trans_segment.get('end', 0)

                        # Check for overlap with speaker segment
                        overlap_start = max(segment['start'], trans_start)
                        overlap_end = min(segment['end'], trans_end)

                        # If there's significant overlap (>50% of transcription segment)
                        if overlap_end > overlap_start:
                            overlap_duration = overlap_end - overlap_start
                            trans_duration = trans_end - trans_start

                            if overlap_duration >= (trans_duration * 0.5):
                                speaker_timestamps.append({
                                    'start': trans_start,
                                    'end': trans_end,
                                    'text': trans_segment.get('text', '')
                                })

                # Sort timestamps by start time
                speaker_timestamps.sort(key=lambda x: x['start'])

                speakers.append({
                    'name': speaker_name,
                    'segments_count': len(segments),
                    'total_speaking_time': sum(s['end'] - s['start'] for s in segments),
                    'timestamps': speaker_timestamps
                })

            logger.info(
                f"Processed {len(speakers)} speakers with mapped timestamps")
            return speakers

        except Exception as e:
            logger.error(f"Failed to process diarization results: {e}")
            # Return fallback single speaker
            return [{
                'name': 'Speaker 1',
                'segments_count': len(transcription_timestamps),
                'total_speaking_time': 0,
                'timestamps': transcription_timestamps
            }]

    async def diarize_audio_file(self, audio_path: Path, transcription_uuid: str) -> Dict:
        """
        Perform speaker diarization on audio file using pyannote.audio.
        
        Args:
            audio_path: Path to the audio file
            transcription_uuid: UUID for tracking
            
        Returns:
            Dict: Diarization results with speaker information
        """
        try:
            if not self.pipeline:
                raise Exception("Diarization pipeline not initialized")

            self.update_status(transcription_uuid, "preprocessing")

            # Preprocess audio for optimal results
            processed_audio_path = self.preprocess_audio(audio_path)

            self.update_status(transcription_uuid, "diarizing")
            logger.info(f"Starting diarization for: {processed_audio_path}")

            # Run diarization pipeline
            start_time = datetime.now()
            diarization = self.pipeline(str(processed_audio_path))
            end_time = datetime.now()

            processing_time = (end_time - start_time).total_seconds()

            # Clean up preprocessed file if it's different from original
            if processed_audio_path != audio_path:
                try:
                    processed_audio_path.unlink()
                except Exception as e:
                    logger.warning(
                        f"Failed to clean up preprocessed file: {e}")

            # Count unique speakers
            speakers_detected = len(set(diarization.labels()))

            logger.info(
                f"Diarization completed: {speakers_detected} speakers detected in {processing_time:.2f}s")

            return {
                "speakers_detected": speakers_detected,
                "processing_time": f"{processing_time:.2f}s",
                "diarization_annotation": diarization,
                "total_duration": diarization.get_timeline().duration()
            }

        except Exception as e:
            self.update_status(transcription_uuid, "failed")
            logger.error(f"Speaker diarization failed: {e}")
            raise Exception(f"Diarization failed: {str(e)}")

    async def save_temp_audio_file(self, audio_content: bytes, transcription_uuid: str, filename: str) -> Path:
        """Save uploaded audio file temporarily for processing."""
        try:
            file_ext = Path(filename).suffix.lower()
            temp_path = Path(f"temp_diarize_{transcription_uuid}{file_ext}")

            with open(temp_path, 'wb') as temp_file:
                temp_file.write(audio_content)

            logger.info(f"Temporary audio file saved: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to save temporary audio file: {e}")
            raise

    async def diarize_speakers(
        self,
        transcription_uuid: str,
        audio_content: bytes,
        filename: str
    ) -> Dict:
        """
        Main function to perform speaker diarization on an existing transcription.
        
        Args:
            transcription_uuid: UUID of the transcription to diarize
            audio_content: Raw audio file content
            filename: Original filename for extension detection
            
        Returns:
            Dict: Results of speaker diarization
        """
        temp_audio_path = None

        try:
            self.update_status(transcription_uuid, "starting")
            logger.info(
                f"Starting speaker diarization for: {transcription_uuid}")

            # Load existing transcription
            transcription_data, json_file_path = self.load_transcription_json(
                transcription_uuid)
            if not transcription_data:
                raise Exception(
                    f"Transcription not found: {transcription_uuid}")

            # Save audio file temporarily
            temp_audio_path = await self.save_temp_audio_file(
                audio_content, transcription_uuid, filename
            )

            # Perform diarization
            diarization_result = await self.diarize_audio_file(temp_audio_path, transcription_uuid)

            # Map diarization to transcription timestamps
            self.update_status(transcription_uuid, "mapping_speakers")
            speakers = self.process_diarization_results(
                diarization_result["diarization_annotation"],
                transcription_data.get("timestamps", [])
            )

            # Assign meaningful speaker names if possible
            speakers = self.assign_speaker_names(speakers, transcription_data)

            # Update transcription with speaker information
            transcription_data["speakers"] = speakers
            transcription_data["diarization_stats"] = {
                "speakers_detected": diarization_result["speakers_detected"],
                "processing_time": diarization_result["processing_time"],
                "total_duration": float(diarization_result["total_duration"])
            }

            # Save updated transcription
            self.save_updated_transcription(transcription_data, json_file_path)

            # Store results for retrieval
            self.results_tracker[transcription_uuid] = {
                "speakers_detected": len(speakers),
                "processing_time": diarization_result["processing_time"],
                "speakers": speakers,
                "updated_transcription": True,
                "stats": transcription_data["diarization_stats"]
            }

            self.update_status(transcription_uuid, "completed")
            logger.info(
                f"Speaker diarization completed for: {transcription_uuid}")

            return {
                "transcription_uuid": transcription_uuid,
                "speakers_detected": len(speakers),
                "processing_time": diarization_result["processing_time"],
                "status": "completed",
                "message": "Speaker diarization completed successfully",
                "speakers": speakers
            }

        except Exception as e:
            self.update_status(transcription_uuid, "failed")
            logger.error(
                f"Speaker diarization failed for {transcription_uuid}: {e}")
            raise Exception(f"Speaker diarization failed: {str(e)}")

        finally:
            # Clean up temporary audio file
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                    logger.info(
                        f"Cleaned up temporary file: {temp_audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")

    def assign_speaker_names(self, speakers: List[Dict], transcription_data: Dict) -> List[Dict]:
        """
        Assign meaningful speaker names based on context and speaking patterns.
        
        For MBA lectures, typically:
        - Speaker with most speaking time = Professor
        - Others = Students/Participants
        """
        try:
            if not speakers:
                return speakers

            # Sort speakers by total speaking time (descending)
            speakers_by_time = sorted(
                speakers,
                key=lambda x: x.get('total_speaking_time', 0),
                reverse=True
            )

            # Get professor name from metadata
            professor_name = transcription_data.get('professor', 'Professor')

            # Assign names based on speaking time and context
            for i, speaker in enumerate(speakers_by_time):
                if i == 0 and speaker.get('total_speaking_time', 0) > 0:
                    # Speaker with most time is likely the professor
                    speaker['name'] = professor_name
                    speaker['role'] = 'Professor'
                else:
                    # Other speakers are students/participants
                    speaker['name'] = f'Student {i}'
                    speaker['role'] = 'Student'

            # Sort back by original order (by first appearance)
            speakers.sort(key=lambda x: x['timestamps']
                          [0]['start'] if x['timestamps'] else 0)

            logger.info(f"Assigned names to {len(speakers)} speakers")
            return speakers

        except Exception as e:
            logger.error(f"Failed to assign speaker names: {e}")
            # Return speakers with generic names
            for i, speaker in enumerate(speakers):
                speaker['name'] = f'Speaker {i + 1}'
                speaker['role'] = 'Unknown'
            return speakers

    def get_speaker_statistics(self, transcription_uuid: str) -> Optional[Dict]:
        """
        Get detailed statistics about speakers in the transcription.
        
        Returns:
            Dict: Speaker statistics including speaking time, segments, etc.
        """
        try:
            results = self.get_diarization_results(transcription_uuid)
            if not results:
                logger.warning(
                    f"No diarization results found for: {transcription_uuid}")
                return None

            speakers = results.get("speakers", [])
            stats = results.get("stats", {})

            total_duration = stats.get("total_duration", 0)
            total_speaking_time = sum(
                s.get('total_speaking_time', 0) for s in speakers)

            speaker_stats = []
            for speaker in speakers:
                speaking_time = speaker.get('total_speaking_time', 0)
                segments_count = speaker.get('segments_count', 0)

                speaker_stats.append({
                    "name": speaker.get('name', 'Unknown'),
                    "role": speaker.get('role', 'Unknown'),
                    "speaking_time_seconds": speaking_time,
                    "speaking_time_percentage": (speaking_time / total_speaking_time * 100) if total_speaking_time > 0 else 0,
                    "segments_count": segments_count,
                    "average_segment_length": speaking_time / segments_count if segments_count > 0 else 0
                })

            return {
                "transcription_uuid": transcription_uuid,
                "total_speakers": len(speakers),
                "processing_time": results.get("processing_time", "Unknown"),
                "total_duration_seconds": total_duration,
                "total_speaking_time_seconds": total_speaking_time,
                "silence_percentage": ((total_duration - total_speaking_time) / total_duration * 100) if total_duration > 0 else 0,
                "speaker_statistics": speaker_stats,
                # Simple quality indicator
                "diarization_quality": "high" if len(speakers) <= 5 else "medium"
            }

        except Exception as e:
            logger.error(f"Failed to generate speaker statistics: {e}")
            return None

    def merge_overlapping_segments(self, segments: List[Dict], threshold: float = 0.5) -> List[Dict]:
        """
        Merge overlapping or very close speaker segments to improve readability.
        
        Args:
            segments: List of speaker segments with start/end times
            threshold: Time threshold for merging (seconds)
            
        Returns:
            List[Dict]: Merged segments
        """
        try:
            if not segments:
                return segments

            # Sort segments by start time
            sorted_segments = sorted(segments, key=lambda x: x.get('start', 0))
            merged_segments = [sorted_segments[0].copy()]

            for current_segment in sorted_segments[1:]:
                last_merged = merged_segments[-1]

                # Check if segments should be merged
                gap = current_segment.get(
                    'start', 0) - last_merged.get('end', 0)

                if gap <= threshold:
                    # Merge segments
                    last_merged['end'] = max(
                        last_merged.get('end', 0),
                        current_segment.get('end', 0)
                    )
                    # Concatenate text with space
                    last_merged['text'] = f"{last_merged.get('text', '')} {current_segment.get('text', '')}".strip(
                    )
                else:
                    # Add as new segment
                    merged_segments.append(current_segment.copy())

            logger.info(
                f"Merged {len(segments)} segments into {len(merged_segments)}")
            return merged_segments

        except Exception as e:
            logger.error(f"Failed to merge segments: {e}")
            return segments

    def export_diarization_results(self, transcription_uuid: str, format: str = "json") -> Optional[str]:
        """
        Export diarization results in various formats.
        
        Args:
            transcription_uuid: UUID of the transcription
            format: Export format ("json", "csv", "txt")
            
        Returns:
            str: Exported data as string
        """
        try:
            results = self.get_diarization_results(transcription_uuid)
            if not results:
                return None

            if format.lower() == "json":
                return json.dumps(results, ensure_ascii=False, indent=2)

            elif format.lower() == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write headers
                writer.writerow(
                    ['Speaker', 'Start Time', 'End Time', 'Duration', 'Text'])

                # Write speaker data
                for speaker in results.get("speakers", []):
                    for timestamp in speaker.get("timestamps", []):
                        writer.writerow([
                            speaker.get('name', 'Unknown'),
                            timestamp.get('start', 0),
                            timestamp.get('end', 0),
                            timestamp.get('end', 0) -
                            timestamp.get('start', 0),
                            timestamp.get('text', '')
                        ])

                return output.getvalue()

            elif format.lower() == "txt":
                output_lines = []
                output_lines.append(f"Speaker Diarization Results")
                output_lines.append(
                    f"Transcription UUID: {transcription_uuid}")
                output_lines.append(
                    f"Speakers Detected: {results.get('speakers_detected', 0)}")
                output_lines.append(
                    f"Processing Time: {results.get('processing_time', 'Unknown')}")
                output_lines.append("-" * 50)

                for speaker in results.get("speakers", []):
                    output_lines.append(
                        f"\n{speaker.get('name', 'Unknown')} ({speaker.get('role', 'Unknown')}):")
                    for timestamp in speaker.get("timestamps", []):
                        start_time = timestamp.get('start', 0)
                        end_time = timestamp.get('end', 0)
                        text = timestamp.get('text', '')
                        output_lines.append(
                            f"[{start_time:.1f}s - {end_time:.1f}s]: {text}")

                return "\n".join(output_lines)

            else:
                logger.error(f"Unsupported export format: {format}")
                return None

        except Exception as e:
            logger.error(f"Failed to export diarization results: {e}")
            return None
