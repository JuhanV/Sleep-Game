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

-- Create RLS policies for profiles
CREATE POLICY "Users can view only their own profiles"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update only their own profiles"
  ON profiles FOR UPDATE
  USING (auth.uid() = id);

-- Create RLS policies for friendships
CREATE POLICY "Users can view only their own friendships"
  ON friendships FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can only add friendships where they are the user"
  ON friendships FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can only delete their own friendships"
  ON friendships FOR DELETE
  USING (auth.uid() = user_id);

-- Create indexes for better query performance
CREATE INDEX idx_profiles_oura_user_id ON profiles (oura_user_id);
CREATE INDEX idx_friendships_user_id ON friendships (user_id);
CREATE INDEX idx_friendships_friend_id ON friendships (friend_id); 