import os
from datetime import datetime

CLASS_TIME_MAPPINGS = {
    "Mon: 8:00 AM": "MBA 505 Leadership",
    "Mon: 9:30 AM": "MBA 530 Operations Management",
    "Mon: 12:30 PM": "MBA 550 Marketing Management",
    "Tue: 8:00 AM": "MBA 501 Corporate Financial Reporting",
    "Tue: 9:30 AM": "MBA 520 Business Finance",
    "Tue: 12:30 PM": "MBA 548 Strategic Human Resource Mgt",
    "Wed: 8:00 AM": "MBA 505 Leadership",
    "Wed: 9:30 AM": "MBA 530 Operations Management",
    "Wed: 12:30 PM": "MBA 550 Marketing Management",
    "Thurs: 8:00 AM": "MBA 500 Career Development",
    "Thurs: 9:30 AM": "MBA 520 Business Finance",
    "Thurs: 12:30 PM": "MBA 548 Strategic Human Resource Mgt",
    "Fri: 9:30 AM": "MBA 593R Management Seminar",
}

def parse_date_from_filename(filename: str) -> str:
    # Assuming the filename format is YYYYMMDDHHMMSS.WAV
    base_name = os.path.splitext(filename)[0]  # Remove file extension
    if len(base_name) != 14 or not base_name.isdigit():
        raise ValueError("Filename does not match expected format YYYYMMDDHHMMSS.WAV")
    
    # hours are in 24-hour format
    
    year = base_name[0:4]
    month = base_name[4:6]
    day = base_name[6:8]
    hour = base_name[8:10]
    minute = base_name[10:12]
    second = base_name[12:14]
    
    formatted_date = f"{year}-{month}-{day}"
    formatted_time = f"{hour}:{minute}:{second}"
    
    return formatted_date, formatted_time

def format_time_string_with_am_pm(time_str: str) -> str:
    hour, minute, second = map(int, time_str.split(':'))
    am_pm = "AM"
    if hour >= 12:
        am_pm = "PM"
        if hour > 12:
            hour -= 12
    elif hour == 0:
        hour = 12
    return f"{hour}:{minute:02} {am_pm}"

def get_day_of_week_from_date(date_str: str) -> str:
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%a")  # Returns abbreviated weekday name, e.g., 'Mon'

def truncate_recording_endtime_to_nearest_quarter(hour: int, minute: int) -> str:
    if minute < 15:
        minute = 0
    elif minute < 30:
        minute = 15
    elif minute < 45:
        minute = 30
    else:
        minute = 45
    return f"{hour:02}:{minute:02}"

def read():
    audio_recording_dir = os.path.join(os.path.expanduser(
    '~'), 'projects', 'lecture-transcriber', 'audio', 'senahs_recorder')
    contents = os.listdir(audio_recording_dir)

    audio_files = [f for f in contents if os.path.isfile(
    os.path.join(audio_recording_dir, f))]
    
    print(f'found {len(audio_files)} audio files in {audio_recording_dir}')
    
    class_list = []
    
    # loop through each audio file and parse the date from the filename and print out the day of the week
    for file in audio_files:
        try:
            date_str, time_str = parse_date_from_filename(file)
            day_of_week = get_day_of_week_from_date(date_str)
            
            # TODO: We will need to truncate the time to the nearest quarter hour, as the recorder will stop sometime between the end of the class and the next quarter hour (before the next class starts)
            
            # hour, minute, second = map(int, time_str.split(':'))
            # truncated_time = truncate_recording_endtime_to_nearest_quarter(hour, minute)
            
            # update this line to use the truncated time
            formatted_time_str = format_time_string_with_am_pm(time_str)
            
            class_key = f"{day_of_week}: {formatted_time_str}"
            class_name = CLASS_TIME_MAPPINGS.get(class_key, "Unknown Class")
            
            class_list.append(f"{date_str}: {class_name}")
            
        except ValueError as e:
            print(f"Error processing file {file}: {e}")
    
    return class_list

def compare():
    pass
