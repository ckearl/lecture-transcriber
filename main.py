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
    
    # 3. compare the recordings on the device to the recordings in supabase
        # if anything is missing, add it to a list of files to transcribe
    
    # 4. return a list of the names of audio files that have been put in google drive
        # if any files are missing, add them to a list of files to upload to google drive
        
    # 5. upload the missing audio files to google drive
        # important to do this first so we can save a copy of the audio file in case anything goes wrong during transcription
        # do not upload files that are already in google drive
        # do not delete any audio files from the recording device (maybe? if she asks for this later)
        
    # 6. transcribe the audio files that are missing transcriptions
        # use whisper api to transcribe the audio files
        # grab the necessary metadata from the /lecture-metadata folder in this repo
        
    # 7. save the transcriptions to supabase
        # look up metadata, save it to metadata table
        # the transcription text will be saved to the textbody table
        # the timestamped insights will be saved to the timestamps table
        # take note of uuid to save these to the correct rows in supabase and for the text insights
        
    # 8. generate text insights for the transcriptions
        # use gemini api to generate text insights
        # review questions, key terms, main ideas, summary
    
    # 9. save the text insights to supabase
        # write these to the textinsights table in supabase
        
    
    

def __init__():
    main()