import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio
import re

import google.generativeai as genai
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextProcessor:
    """
    Text processing using Google Gemini API.
    
    This class handles:
    1. Generating main ideas from transcription text
    2. Creating lecture summaries
    3. Extracting keywords and key concepts
    4. Generating review questions
    5. Updating transcription JSON with processed content
    6. Saving insights to Supabase
    """

    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """Initialize Google Gemini client and Supabase client."""
        self.client = None
        self.status_tracker: Dict[str, str] = {}
        self.results_tracker: Dict[str, Dict] = {}
        self.transcriptions_dir = Path("transcriptions")

        # Configuration for processing
        self.max_chunk_size = 30000  # Characters per chunk for Gemini
        self.max_retries = 3
        self.retry_delay = 2  # seconds

        # Initialize Supabase client
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_ANON_KEY')

        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(
                self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized successfully")
        else:
            logger.error("Supabase credentials not found")
            self.supabase = None

        self._initialize_gemini()

    def _initialize_gemini(self):
        """Initialize Google Gemini API client."""
        try:
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if not api_key:
                logger.error(
                    "GOOGLE_GEMINI_API_KEY environment variable not set")
                raise Exception("Google Gemini API key not configured")

            genai.configure(api_key=api_key)

            # Use Gemini 2.5 Flash - best price/performance for lecture analysis
            self.client = genai.GenerativeModel('gemini-2.5-flash')

            # Configure generation parameters for academic content
            self.generation_config = genai.types.GenerationConfig(
                temperature=0.3,  # Lower temperature for more consistent academic analysis
                top_p=0.8,
                top_k=40,
                max_output_tokens=4096,
                candidate_count=1
            )

            logger.info(
                "Google Gemini API client initialized successfully with gemini-2.5-flash")

        except Exception as e:
            logger.error(f"Failed to initialize Google Gemini API: {e}")
            self.client = None
            raise

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split long transcriptions into manageable chunks for API processing.
        
        Args:
            text: Full transcription text
            
        Returns:
            List of text chunks that respect sentence boundaries
        """
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentences to maintain context
        sentences = re.split(r'[.!?]+\s+', text)

        for sentence in sentences:
            # Add sentence if it fits in current chunk
            if len(current_chunk + sentence) <= self.max_chunk_size:
                current_chunk += sentence + ". "
            else:
                # Save current chunk and start new one
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "

        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    async def _make_gemini_request(self, prompt: str, retries: int = None) -> str:
        """
        Make a request to Gemini API with retry logic.
        
        Args:
            prompt: The prompt to send to Gemini
            retries: Number of retries (uses self.max_retries if None)
            
        Returns:
            Generated response text
        """
        if retries is None:
            retries = self.max_retries

        for attempt in range(retries + 1):
            try:
                response = await asyncio.to_thread(
                    self.client.generate_content,
                    prompt,
                    generation_config=self.generation_config
                )

                if response.text:
                    return response.text.strip()
                else:
                    logger.warning(
                        f"Empty response from Gemini on attempt {attempt + 1}")

            except Exception as e:
                logger.warning(
                    f"Gemini API error on attempt {attempt + 1}: {e}")
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise Exception(
                        f"Failed to get response from Gemini after {retries + 1} attempts: {e}")

        raise Exception("No valid response received from Gemini")

    def get_processing_status(self, lecture_uuid: str) -> str:
        """Get the current status of text processing."""
        return self.status_tracker.get(lecture_uuid, "not_started")

    def get_processed_results(self, lecture_uuid: str) -> Optional[Dict]:
        """Get the text processing results."""
        return self.results_tracker.get(lecture_uuid, None)

    def update_status(self, lecture_uuid: str, status: str):
        """Update text processing status."""
        self.status_tracker[lecture_uuid] = status
        logger.info(
            f"Text processing status updated for {lecture_uuid}: {status}")

    def save_insights_to_supabase(self, lecture_uuid: str, insights: Dict[str, Any]):
        """Save text insights to Supabase."""
        if not self.supabase:
            raise Exception("Supabase client not initialized")

        try:
            insights_data = {
                "lecture_id": lecture_uuid,
                "summary": insights["summary"],
                "key_terms": insights["keywords"],
                "main_ideas": insights["main_ideas"],
                "review_questions": insights["questions_to_review"]
            }

            result = self.supabase.table(
                "text_insights").insert(insights_data).execute()
            logger.info(
                f"Saved text insights to Supabase for lecture: {lecture_uuid}")

        except Exception as e:
            logger.error(f"Failed to save insights to Supabase: {e}")
            raise Exception(f"Supabase insights save failed: {str(e)}")

    def load_transcription_json(self, transcription_uuid: str) -> tuple:
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
                                return data, json_file
                        except (json.JSONDecodeError, KeyError):
                            continue
            return None, None
        except Exception as e:
            logger.error(f"Failed to load transcription: {e}")
            return None, None

    def save_updated_transcription(self, transcription_data: Dict, file_path: Path):
        """Save updated transcription with processed text."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated transcription saved: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save updated transcription: {e}")
            raise

    def _create_main_ideas_prompt(self, text_chunks: List[str], context: Dict) -> str:
        """Create prompt for extracting main ideas."""
        class_name = context.get('class', 'Business')
        professor = context.get('professor', 'Professor')
        title = context.get('title', 'Lecture')

        if len(text_chunks) == 1:
            text_content = text_chunks[0][:8000]  # Limit for single chunk
        else:
            # For multiple chunks, create a summary of each
            text_content = "\n\n".join([f"Section {i+1}: {chunk[:2000]}..."
                                        for i, chunk in enumerate(text_chunks[:3])])

        return f"""
You are analyzing a {class_name} lecture by {professor} titled "{title}".

Please identify the 6-8 most important main ideas or key concepts discussed in this lecture. Focus on:
- Core business concepts and frameworks
- Key theories or models presented
- Strategic insights or principles
- Important methodologies or approaches
- Critical takeaways for MBA students

Lecture content:
{text_content}

Provide exactly 6-8 main ideas as a numbered list. Each idea should be concise (8-12 words) but comprehensive enough to capture the essence of the concept. There should be no additional explanation or commentary. Provide only the list.

Format your response as:
1. [Main idea 1]
2. [Main idea 2]
...etc.
"""

    def _create_summary_prompt(self, text_chunks: List[str], context: Dict) -> str:
        """Create prompt for generating lecture summary."""
        class_name = context.get('class', 'Business')
        professor = context.get('professor', 'Professor')
        title = context.get('title', 'Lecture')

        if len(text_chunks) == 1:
            text_content = text_chunks[0]
        else:
            # For multiple chunks, include first and last chunks fully, summarize middle
            text_content = text_chunks[0]
            if len(text_chunks) > 2:
                text_content += f"\n\n[Middle sections contain discussions of: {', '.join(context.get('keywords', ['various topics']))}]\n\n"
            text_content += text_chunks[-1]

        return f"""
Create a comprehensive summary of this {class_name} lecture by {professor} on "{title}".

Your summary should be 150-250 words and include:
1. Brief introduction to the topic/context
2. Main arguments and key points presented
3. Important frameworks, models, or methodologies discussed
4. Practical applications or case studies mentioned
5. Key conclusions and takeaways for MBA students

Focus on content that would be most valuable for exam preparation and practical business application. There should be no supplementary words, introductions, or conclusions outside of the summary itself.

Lecture content:
{text_content[:15000]}

Write a well-structured, professional summary suitable for MBA students preparing for exams.
"""

    def _create_keywords_prompt(self, text_chunks: List[str], context: Dict) -> str:
        """Create prompt for extracting keywords."""
        class_name = context.get('class', 'Business')

        # Sample from multiple chunks if available
        if len(text_chunks) > 1:
            sample_text = text_chunks[0][:3000] + \
                "\n\n" + text_chunks[-1][:3000]
        else:
            sample_text = text_chunks[0][:6000]

        return f"""
Extract 10-15 important keywords and key terms from this {class_name} lecture.

Focus on:
- Business terminology and jargon
- Frameworks and models (e.g., SWOT, Porter's Five Forces, etc.)
- Technical terms specific to the subject area
- Important concepts that would appear in exams
- Methodologies and analytical tools
- Key performance indicators or metrics
- Strategic concepts and approaches

Avoid common words. Focus on substantive business and academic terms.

Lecture content:
{sample_text}

Provide exactly 12-15 keywords as a simple comma-separated list (no numbers or bullets). There should be no additonal words like "Keywords include" or "The keywords are". Only provide the list. If you can, try to limit redundant keywords.
Example format: Strategic Planning, Market Analysis, Competitive Advantage, SWOT Analysis, ...
"""

    def _create_questions_prompt(self, text_chunks: List[str], context: Dict, main_ideas: List[str]) -> str:
        """Create prompt for generating review questions."""
        class_name = context.get('class', 'Business')
        title = context.get('title', 'Lecture')

        # Use main ideas to guide question generation
        ideas_text = "\n".join([f"- {idea}" for idea in main_ideas])

        # Sample key content for questions
        if len(text_chunks) > 1:
            content_sample = text_chunks[0][:4000] + \
                "\n...\n" + text_chunks[-1][:4000]
        else:
            content_sample = text_chunks[0][:8000]

        return f"""
Generate 6-8 review questions for this {class_name} lecture on "{title}".

Main concepts covered:
{ideas_text}

Create a mix of question types:
- 3-4 factual/recall questions (What is...? Define...?)
- 4-5 analytical questions (How does...? Why is...? Compare...?)
- 3-4 application questions (How would you apply...? What would happen if...?)

Questions should:
- Be suitable for MBA-level study and exam preparation
- Cover the most important concepts from the lecture
- Encourage critical thinking about business applications
- Be clear and specific enough to guide study

Lecture sample:
{content_sample}

Provide exactly 10-12 questions as a numbered list. There should be no additional explanation or commentary, no introductory or concluding text. Only provide the list of questions. Example format:
1. [Question 1]
2. [Question 2]
...etc.
"""

    def _parse_list_response(self, response: str, expected_count: int = None) -> List[str]:
        """Parse numbered list response from Gemini."""
        lines = response.strip().split('\n')
        items = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove numbering (1., 2., -, •, etc.)
            clean_line = re.sub(r'^\d+\.?\s*', '', line)
            clean_line = re.sub(r'^[-•]\s*', '', clean_line)

            # Avoid empty or very short items
            if clean_line and len(clean_line) > 3:
                items.append(clean_line)

        return items

    def _parse_keywords_response(self, response: str) -> List[str]:
        """Parse comma-separated keywords from Gemini response."""
        # Remove any introductory text and get the keywords
        lines = response.strip().split('\n')
        keywords_line = ""

        for line in lines:
            if ',' in line and len(line.split(',')) > 3:  # Likely the keywords line
                keywords_line = line
                break

        if not keywords_line:
            keywords_line = response.strip()

        # Split by commas and clean up
        keywords = [keyword.strip() for keyword in keywords_line.split(',')]
        keywords = [kw for kw in keywords if kw and len(
            kw) > 2]  # Filter short/empty items

        return keywords[:15]  # Limit to 15 keywords

    async def generate_main_ideas(self, transcription_text: str, context: Dict) -> List[str]:
        """Generate main ideas from transcription using Google Gemini."""
        try:
            text_chunks = self._chunk_text(transcription_text)
            prompt = self._create_main_ideas_prompt(text_chunks, context)

            response = await self._make_gemini_request(prompt)
            main_ideas = self._parse_list_response(response, expected_count=8)

            # Ensure we have at least 5 ideas and at most 8
            if len(main_ideas) < 5:
                main_ideas.extend(
                    [f"Additional concept {i}" for i in range(5 - len(main_ideas))])
            elif len(main_ideas) > 8:
                main_ideas = main_ideas[:8]

            logger.info(f"Generated {len(main_ideas)} main ideas")
            return main_ideas

        except Exception as e:
            logger.error(f"Failed to generate main ideas: {e}")
            return [
                "Error generating main ideas - please check API configuration",
                f"Class: {context.get('class', 'Unknown')}",
                f"Topic: {context.get('title', 'Unknown')}"
            ]

    async def generate_summary(self, transcription_text: str, context: Dict) -> str:
        """Generate lecture summary using Google Gemini."""
        try:
            text_chunks = self._chunk_text(transcription_text)
            prompt = self._create_summary_prompt(text_chunks, context)

            response = await self._make_gemini_request(prompt)

            # Clean up the response
            summary = response.strip()

            # Ensure reasonable length (aim for 400-500 words)
            words = summary.split()
            if len(words) > 600:
                summary = ' '.join(words[:550]) + "..."

            logger.info(f"Generated summary with {len(summary.split())} words")
            return summary

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            class_name = context.get('class', 'Unknown Class')
            title = context.get('title', 'Lecture')
            return f"""Error generating summary for the {class_name} lecture on {title}. 
            
Please check the Google Gemini API configuration and ensure the GOOGLE_GEMINI_API_KEY environment variable is properly set. The transcription was successfully created but AI analysis could not be completed.

To resolve this issue:
1. Verify your Google Gemini API key is valid
2. Ensure you have sufficient API quota
3. Check your network connectivity
4. Retry the text processing operation"""

    async def extract_keywords(self, transcription_text: str, context: Dict) -> List[str]:
        """Extract keywords and key terms using Google Gemini."""
        try:
            text_chunks = self._chunk_text(transcription_text)
            prompt = self._create_keywords_prompt(text_chunks, context)

            response = await self._make_gemini_request(prompt)
            keywords = self._parse_keywords_response(response)

            # Ensure we have a reasonable number of keywords
            if len(keywords) < 8:
                # Add some default business terms based on class
                class_name = context.get('class', 'business').lower()
                default_terms = {
                    'finance': ['Financial Analysis', 'Capital Structure', 'Risk Management'],
                    'marketing': ['Market Segmentation', 'Brand Strategy', 'Consumer Behavior'],
                    'operations': ['Process Optimization', 'Supply Chain', 'Quality Management'],
                    'strategy': ['Competitive Advantage', 'Strategic Planning', 'Market Analysis']
                }

                additional = default_terms.get(
                    class_name, ['Business Strategy', 'Management', 'Analysis'])
                keywords.extend(additional[:15-len(keywords)])

            logger.info(f"Extracted {len(keywords)} keywords")
            return keywords[:15]  # Limit to 15

        except Exception as e:
            logger.error(f"Failed to extract keywords: {e}")
            class_name = context.get('class', 'business')
            return [
                f"{class_name} Analysis",
                "Key Concepts",
                "Strategic Framework",
                "Management Principles",
                "Business Applications"
            ]

    async def generate_review_questions(self, transcription_text: str, context: Dict, main_ideas: List[str] = None) -> List[str]:
        """Generate review questions using Google Gemini."""
        try:
            if not main_ideas:
                main_ideas = await self.generate_main_ideas(transcription_text, context)

            text_chunks = self._chunk_text(transcription_text)
            prompt = self._create_questions_prompt(
                text_chunks, context, main_ideas)

            response = await self._make_gemini_request(prompt)
            questions = self._parse_list_response(response, expected_count=12)

            # Ensure we have enough questions
            if len(questions) < 8:
                class_name = context.get('class', 'Business')
                title = context.get('title', 'this topic')
                additional_questions = [
                    f"What are the key takeaways from this {class_name} lecture?",
                    f"How do the concepts discussed apply to real-world business scenarios?",
                    f"What frameworks or models were introduced in relation to {title}?",
                    f"How might these principles be tested in an exam setting?"
                ]
                questions.extend(additional_questions[:12-len(questions)])

            logger.info(f"Generated {len(questions)} review questions")
            return questions[:12]  # Limit to 12

        except Exception as e:
            logger.error(f"Failed to generate review questions: {e}")
            class_name = context.get('class', 'Business')
            title = context.get('title', 'the lecture topic')
            return [
                f"What are the main concepts covered in this {class_name} lecture?",
                f"How do the principles discussed relate to {title}?",
                "What practical applications were mentioned?",
                "How might this content appear on an exam?",
                "What are the key frameworks or models presented?"
            ]

    async def process_text(self, lecture_uuid: str, transcription_text: str, context: Dict) -> Dict:
        """
        Main function to process transcription text with Google Gemini.
        
        This function:
        1. Generates main ideas, summary, keywords, and questions
        2. Updates the transcription JSON with processed content (if available)
        3. Saves insights to Supabase
        4. Returns processing results
        """
        if not self.client:
            raise Exception(
                "Google Gemini API not properly initialized. Check your GOOGLE_GEMINI_API_KEY environment variable.")

        try:
            self.update_status(lecture_uuid, "starting")

            logger.info(
                f"Processing {len(transcription_text)} characters for {context['class']} lecture")

            # Generate all text processing elements
            self.update_status(lecture_uuid, "generating_main_ideas")
            main_ideas = await self.generate_main_ideas(transcription_text, context)

            self.update_status(lecture_uuid, "generating_summary")
            summary = await self.generate_summary(transcription_text, context)

            self.update_status(lecture_uuid, "extracting_keywords")
            keywords = await self.extract_keywords(transcription_text, context)

            self.update_status(lecture_uuid, "generating_questions")
            questions = await self.generate_review_questions(transcription_text, context, main_ideas)

            # Prepare insights for Supabase
            insights = {
                "main_ideas": main_ideas,
                "summary": summary,
                "keywords": keywords,
                "questions_to_review": questions
            }

            # Save insights to Supabase
            self.update_status(lecture_uuid, "saving_to_database")
            self.save_insights_to_supabase(lecture_uuid, insights)

            # Try to update local JSON file if it exists (optional)
            try:
                # This is now optional since we're working directly with Supabase
                transcription_data, json_file_path = self.load_transcription_json(
                    lecture_uuid)
                if transcription_data and json_file_path:
                    transcription_data.update(insights)
                    self.save_updated_transcription(
                        transcription_data, json_file_path)
                    logger.info("Updated local JSON file with insights")
            except Exception as e:
                logger.warning(f"Could not update local JSON file: {e}")

            # Store results for retrieval
            processing_results = {
                **insights,
                "processing_complete": True
            }

            self.results_tracker[lecture_uuid] = processing_results
            self.update_status(lecture_uuid, "completed")

            logger.info(
                f"Text processing completed successfully for: {lecture_uuid}")

            return {
                "lecture_uuid": lecture_uuid,
                "status": "completed",
                "message": "Text processing completed successfully",
                "results": processing_results
            }

        except Exception as e:
            self.update_status(lecture_uuid, "failed")
            logger.error(
                f"Text processing failed for {lecture_uuid}: {e}")
            raise Exception(f"Text processing failed: {str(e)}")

    def run(self, lecture_uuid: str, transcription_text: str, context: Dict) -> Dict:
        """
        Sync wrapper for main.py so you can call one method directly.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If inside a running event loop, create a new one in a thread
            return asyncio.run(self.process_text(lecture_uuid, transcription_text, context))
        else:
            return loop.run_until_complete(self.process_text(lecture_uuid, transcription_text, context))

    def get_processing_statistics(self, lecture_uuid: str) -> Optional[Dict]:
        """
        Get statistics about the text processing results.
        """
        results = self.get_processed_results(lecture_uuid)
        if not results:
            return None

        return {
            "main_ideas_count": len(results.get("main_ideas", [])),
            "keywords_count": len(results.get("keywords", [])),
            "questions_count": len(results.get("questions_to_review", [])),
            "summary_word_count": len(results.get("summary", "").split()),
            "processing_status": self.get_processing_status(lecture_uuid),
        }
