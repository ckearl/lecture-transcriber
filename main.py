from gdrive.read import loop as gdrive_read
from gdrive.upload import upload as gdrive_upload
from local_files.read import read as local_read
from transcribe.transcribe import TranscriptionProcessor
from text_insights.process import TextProcessor


def read_supabase_data():
    # Placeholder function to read data from Supabase
    print("Reading data from Supabase...")
    # Add actual Supabase reading logic here
    return []

def main():
    print('welcome to the lecture transcriber!')
    
    # 1. read in the existing supabase data
    
    
    # 2. read in the recorded audio file
        # - the file will be in the folder of the audio recording device when plugged into the computer
        # - the file name will be the date and time of the recording (YYYYMMDDHHMMSS.WAV)
        # - the file format will be WAV
    
    # get list of file names in the folder ~/projects/lecture-transcriber/audio/senahs_recorder/
    
    # local_read()
    
    
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