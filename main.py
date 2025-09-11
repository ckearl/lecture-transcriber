import os
import pyfiglet

from db_supabase.upload import LectureUploader
from db_supabase.read import LectureReader
from gdrive.read import loop as gdrive_read
from gdrive.upload import upload as gdrive_upload
from local_files.read import read as local_read
from transcribe.transcribe import TranscriptionProcessor
from text_insights.process import TextProcessor

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

def main():
    text = "Hi my love <3"

    ascii_art = pyfiglet.figlet_format(text, font="larry3d", width=999)
    print(ascii_art)

    #1. read in supabase to get list of recorded audio files already transcribed
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.")
        return

    reader = LectureReader(SUPABASE_URL, SUPABASE_KEY)
    
    sb_lecture_list = reader.fetch_lecture_list()
    curated_sb_lecture_list = []

    if sb_lecture_list is not None:
        # print("✅ Successfully fetched lecture list:")
        for lecture in sb_lecture_list:
            curated_sb_lecture_list.append(f"{lecture['date']}: {lecture['class_number']}")
            # print(
            #     f"  - Title: {lecture['title']}, "
            #     f"Class: {lecture['class_number']}, "
            #     f"Date: {lecture['date']}"
            # )    
    
    # 2. read in the recorded audio file
        # - the file will be in the folder of the audio recording device when plugged into the computer
        # - the file name will be the date and time of the recording (YYYYMMDDHHMMSS.WAV)
        # - the file format will be WAV
    
    # get list of file names in the folder ~/projects/lecture-transcriber/audio/senahs_recorder/
    
    local_lecture_list = local_read()
    
    lectures_to_upload = []
    
    for lecture in local_lecture_list:
        if lecture in curated_sb_lecture_list:
            print(f"{lecture} found in both local and supabase lists")
        else:
            print(f"{lecture} NOT found in supabase list")
            lectures_to_upload.append(lecture)
            
    
    
    # 3. compare the recordings on the device to the recordings in supabase
        # if anything is missing, add it to a list of files to transcribe
    
    # 4. return a list of the names of audio files that have been put in google drive
        # if any files are missing, add them to a list of files to upload to google drive
        
    # gdrive_files = gdrive_read()
        
        
    # 5. upload the missing audio files to google drive
        # important to do this first so we can save a copy of the audio file in case anything goes wrong during transcription
        # do not upload files that are already in google drive
        # do not delete any audio files from the recording device (maybe? if she asks for this later)
    
    
        
    # gdrive_upload(audio_file_path='/Users/toph/projects/lecture-transcriber/audio/partials/econ159_07_092607_split_007.mp3', file_name='econ159_07_092607_split_003.mp3')
        
    # 6. transcribe the audio files that are missing transcriptions
        # use whisper api to transcribe the audio files
        # grab the necessary metadata from the /lecture-metadata folder in this repo
        
    # transcription_processor = TranscriptionProcessor()
        
    # 7. save the transcriptions to supabase
        # look up metadata, save it to metadata table
        # the transcription text will be saved to the textbody table
        # the timestamped insights will be saved to the timestamps table
        # take note of uuid to save these to the correct rows in supabase and for the text insights
        
    # 8. generate text insights for the transcriptions
        # use gemini api to generate text insights
        # review questions, key terms, main ideas, summary
        
    # text_processor = TextProcessor()
    
    # 9. save the text insights to supabase
        # write these to the textinsights table in supabase
        
    
    

if __name__ == '__main__':
    main()