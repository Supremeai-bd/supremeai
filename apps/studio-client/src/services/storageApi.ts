// Frontend R2 Storage API

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Mock auth token getter
const getAuthToken = () => {
    return localStorage.getItem('token') || 'dummy-token';
};

export const uploadFileToR2 = async (file: File) => {
    try {
        // 1. Get presigned upload URL from backend
        const response = await fetch(${API_BASE_URL}/api/v1/media/generate-upload-url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': Bearer ${getAuthToken()}
            },
            body: JSON.stringify({
                file_name: file.name,
                file_type: file.type,
                folder: 'custom_skills'
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate upload URL');
        }

        const { upload_url, file_path } = await response.json();

        // 2. Upload file directly to Cloudflare R2
        const uploadResponse = await fetch(upload_url, {
            method: 'PUT',
            headers: {
                'Content-Type': file.type,
            },
            body: file
        });

        if (!uploadResponse.ok) {
            throw new Error('Failed to upload file directly to R2');
        }

        // 3. Return the file path to be saved in Supabase
        return file_path;

    } catch (error) {
        console.error('Upload Error:', error);
        throw error;
    }
};
