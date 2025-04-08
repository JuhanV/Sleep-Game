-- Drop existing tables if they exist (to ensure clean setup)
DROP TABLE IF EXISTS friendships;
DROP TABLE IF EXISTS profiles;

-- Create profiles table
CREATE TABLE profiles (
  id UUID PRIMARY KEY,
  oura_user_id TEXT UNIQUE NOT NULL,
  email TEXT,
  display_name TEXT,
  oura_tokens TEXT,
  avg_sleep_score NUMERIC,
  last_sleep_score NUMERIC,
  last_login TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Create friendships table
CREATE TABLE friendships (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  friend_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  UNIQUE(user_id, friend_id)
);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE friendships ENABLE ROW LEVEL SECURITY;

-- Create open policy for profiles (for development)
-- This allows any operation on profiles without authentication
-- Replace these with stricter policies for production
DROP POLICY IF EXISTS "Allow all operations on profiles" ON profiles;
CREATE POLICY "Allow all operations on profiles" 
  ON profiles 
  USING (true) 
  WITH CHECK (true);

-- Create open policy for friendships (for development)
-- This allows any operation on friendships without authentication
-- Replace these with stricter policies for production
DROP POLICY IF EXISTS "Allow all operations on friendships" ON friendships;
CREATE POLICY "Allow all operations on friendships" 
  ON friendships 
  USING (true) 
  WITH CHECK (true);

-- Create indexes for better query performance
CREATE INDEX idx_profiles_oura_user_id ON profiles (oura_user_id);
CREATE INDEX idx_friendships_user_id ON friendships (user_id);
CREATE INDEX idx_friendships_friend_id ON friendships (friend_id); 