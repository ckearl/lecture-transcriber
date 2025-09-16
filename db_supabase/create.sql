-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Lectures table (metadata)
CREATE TABLE lectures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    professor VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    duration_seconds INTEGER NOT NULL,
    class_number VARCHAR(50) NOT NULL,
    language VARCHAR(10) DEFAULT 'en-US',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Speakers table
CREATE TABLE speakers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE,
    speaker_name VARCHAR(100) NOT NULL,
    speaker_order INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(lecture_id, speaker_name),
    UNIQUE(lecture_id, speaker_order)
);

-- Transcript segments with timestamps
CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE,
    start_time DECIMAL(10,3) NOT NULL, -- Supports millisecond precision
    end_time DECIMAL(10,3) NOT NULL,
    text TEXT NOT NULL,
    speaker_name VARCHAR(100),
    segment_order INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_time_range CHECK (end_time > start_time),
    UNIQUE(lecture_id, segment_order)
);

-- Full text body (for easy searching)
CREATE TABLE lecture_texts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE UNIQUE,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI-generated insights
CREATE TABLE text_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE UNIQUE,
    summary TEXT NOT NULL,
    key_terms TEXT[] NOT NULL,
    main_ideas TEXT[] NOT NULL,
    review_questions TEXT[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);