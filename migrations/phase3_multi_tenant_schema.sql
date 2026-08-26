-- G8: User API Keys
CREATE TABLE IF NOT EXISTS user_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, provider)
);

-- Enable RLS
ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own keys"
ON user_keys
FOR ALL
USING (auth.uid()::text = user_id);

-- G10: Conversations
-- বাংলা: আগে এখানে DROP TABLE IF EXISTS messages/conversations CASCADE ছিল --
-- migration_safety_diff.py দিয়ে ধরা পড়েছে এটা CRITICAL destructive (production-এ
-- চললে সব ইউজার চ্যাট হিস্টোরি স্থায়ীভাবে মুছে যেত)। DROP সরিয়ে দেওয়া হলো --
-- নিচের CREATE TABLE IF NOT EXISTS ইতিমধ্যেই idempotent, তাই DROP আসলে দরকারই
-- ছিল না নতুন environment-এ প্রথমবার চালানোর জন্য।

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own conversations"
ON conversations
FOR ALL
USING (auth.uid()::text = user_id);

CREATE POLICY "Users can manage messages in their conversations"
ON messages
FOR ALL
USING (
    EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.id = messages.conversation_id
        AND c.user_id = auth.uid()::text
    )
);
