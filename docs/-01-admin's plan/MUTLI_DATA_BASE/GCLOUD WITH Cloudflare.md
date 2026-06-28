সুপ্রিম এআই (SupremeAI) প্রজেক্টের জিরো মেইনটেইন্যান্স এবং ক্লাউড-ফার্স্ট আর্কিটেকচারের জন্য Cloudflare R2 একটি নিখুঁত সিদ্ধান্ত। এর 10GB ফ্রি স্টোরেজ এবং আনলিমিটেড ইগ্রেস (Egress) ব্যান্ডউইথ আপনার প্রজেক্টের হোস্টিং খরচ পুরোপুরি শূন্যে নামিয়ে আনবে।

গুগল ক্লাউড রান (Cloud Run)-এর মেমোরি এবং প্রসেসিং পাওয়ার বাঁচাতে আমরা এখানে Pre-signed URL মেকানিজম ব্যবহার করব। এতে ইউজাররা ফাইল ব্যাকএন্ডের ভেতর দিয়ে না পাঠিয়ে, সরাসরি ক্লাউডফ্লেয়ারের সার্ভারে আপলোড করতে পারবেন।

নিচে Cloudflare R2-এর সম্পূর্ণ সেটআপ এবং ইন্টিগ্রেশন প্ল্যান ধাপে ধাপে দেওয়া হলো

ধাপ ১ Cloudflare ড্যাশবোর্ডে R2 বাকেট সেটআপ
Cloudflare ড্যাশবোর্ডে লগইন করে বামদিকের মেনু থেকে R2 Object Storage-এ যান।

Create Bucket-এ ক্লিক করে একটি বাকেট তৈরি করুন (যেমন supremeai-assets)। Location Automatic রাখতে পারেন।

বাকেট তৈরি হলে ডানদিকে Manage R2 API Tokens-এ ক্লিক করুন।

Create API token নির্বাচন করুন

Permissions Object Read & Write নির্বাচন করুন।

Specify bucket(s) শুধু আপনার তৈরি করা বাকেটটি সিলেক্ট করুন (সিকিউরিটির জন্য)।

টোকেন তৈরি হলে নিচের ৩টি তথ্য কপি করে নিরাপদে সংরক্ষণ করুন

Access Key ID

Secret Access Key

S3 API Endpoint (এটি দেখতে অনেকটা এমন হবে httpsaccount_id.r2.cloudflarestorage.com)

ধাপ ২ এনভায়রনমেন্ট ভ্যারিয়েবল ও সিক্রেট সিঙ্ক
আপনার লোকাল .env ফাইলে নিচের ভ্যারিয়েবলগুলো যুক্ত করুন। প্রোডাকশনের জন্য এগুলোকে ফায়ারবেস ফায়ারস্টোরের primary_vault ডকুমেন্টে অ্যাড করে দিন, যাতে আপনার sync_secrets.py স্ক্রিপ্টটি এগুলোকে অটোমেটিক পুল করে নিতে পারে।

Code snippet
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY=your_r2_access_key
R2_SECRET_KEY=your_r2_secret_key
R2_BUCKET_NAME=supremeai-assets
R2_PUBLIC_URL=httpspub-xxxxxxxx.r2.dev # (অপশনাল পাবলিক অ্যাক্সেসের জন্য Custom Domain)
ধাপ ৩ ব্যাকএন্ডে Boto3 (S3 Client) ইন্টিগ্রেশন
R2 যেহেতু S3-কমপ্যাটিবল, তাই পাইথনের অফিশিয়াল এডব্লিউএস লাইব্রেরি boto3 এখানে দারুণ কাজ করবে।

১. লাইব্রেরি ইনস্টল করুন
আপনার backend ডিরেক্টরিতে গিয়ে ডিপেনডেন্সি আপডেট করুন

Bash
poetry add boto3
২. স্টোরেজ সার্ভিস ক্লাস তৈরি করুন (backendstorager2_storage_client.py)

Python
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from loguru import logger

class R2StorageClient
    def __init__(self)
        account_id = os.getenv(R2_ACCOUNT_ID)
        access_key = os.getenv(R2_ACCESS_KEY)
        secret_key = os.getenv(R2_SECRET_KEY)
        self.bucket_name = os.getenv(R2_BUCKET_NAME)
        
        # Cloudflare R2 Endpoint
        endpoint_url = fhttps{account_id}.r2.cloudflarestorage.com

        self.s3_client = boto3.client(
            s3,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=auto, # R2 uses 'auto'
            config=Config(signature_version=s3v4)
        )

    def generate_presigned_upload_url(self, object_name str, file_type str, expiration=3600)
        
        ক্লায়েন্টকে সরাসরি R2-তে ফাইল আপলোড করার জন্য একটি সাময়িক URL তৈরি করে দেয়।
        
        try
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket' self.bucket_name,
                    'Key' object_name,
                    'ContentType' file_type
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e
            logger.error(fError generating presigned URL {e})
            return None

    def generate_presigned_download_url(self, object_name str, expiration=3600)
        
        প্রাইভেট ফাইল ডাউনলোডের জন্য টেম্পোরারি URL জেনারেট করে।
        
        try
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket' self.bucket_name,
                    'Key' object_name
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e
            logger.error(fError generating download URL {e})
            return None
ধাপ ৪ FastAPI রাউটার তৈরি (backendapiroutesmedia.py)
এবার ফ্রন্টএন্ড বা স্টুডিও ক্লায়েন্ট থেকে এই URL রিকোয়েস্ট করার জন্য একটি এপিআই এন্ডপয়েন্ট তৈরি করুন।

Python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from storage.r2_storage_client import R2StorageClient
from core.auth_middleware import require_auth_token # আপনার কাস্টম অথ মিডলওয়্যার

router = APIRouter()
storage_client = R2StorageClient()

class UploadRequest(BaseModel)
    file_name str
    file_type str
    folder str = skills_bundles # ডিফল্ট ফোল্ডার

@router.post(generate-upload-url)
async def get_upload_url(request UploadRequest, user=Depends(require_auth_token))
    # ইউনিক ফাইলের পাথ তৈরি (যাতে নাম ক্ল্যাশ না করে)
    import uuid
    safe_filename = f{request.folder}{user['id']}{uuid.uuid4().hex}_{request.file_name}
    
    upload_url = storage_client.generate_presigned_upload_url(
        object_name=safe_filename,
        file_type=request.file_type
    )
    
    if not upload_url
        raise HTTPException(status_code=500, detail=Could not generate upload URL)
        
    return {
        upload_url upload_url,
        file_path safe_filename, # আপলোড শেষে ডাটাবেসে সেভ করার জন্য
        public_url f{os.getenv('R2_PUBLIC_URL')}{safe_filename} # যদি বাকেট পাবলিক হয়
    }
ধাপ ৫ React Studio Client থেকে সরাসরি আপলোড
ফ্রন্টএন্ড (ReactVite) থেকে ফাইলটি ব্যাকএন্ডে না পাঠিয়ে, জেনারেট করা Pre-signed URL ব্যবহার করে সরাসরি Cloudflare R2-তে আপলোড করার লজিক

JavaScript
 srcservicesstorageApi.ts

export const uploadFileToR2 = async (file File) = {
    try {
         ১. ব্যাকএন্ড থেকে প্রে-সাইন্ড আপলোড ইউআরএল নিয়ে আসা
        const response = await fetch(`${API_BASE_URL}apiv1mediagenerate-upload-url`, {
            method 'POST',
            headers {
                'Content-Type' 'applicationjson',
                'Authorization' `Bearer ${getAuthToken()}`
            },
            body JSON.stringify({
                file_name file.name,
                file_type file.type,
                folder custom_skills
            })
        });
        
        const { upload_url, file_path } = await response.json();

         ২. সরাসরি Cloudflare R2-তে ফাইল আপলোড (ব্যাকএন্ড বাইপাস করে)
        const uploadResponse = await fetch(upload_url, {
            method 'PUT',
            headers {
                'Content-Type' file.type,
            },
            body file
        });

        if (!uploadResponse.ok) {
            throw new Error(Failed to upload file directly to R2);
        }

         ৩. সফল হলে ফাইলের পাথ রিটার্ন করা (যা Supabase ডাটাবেসে সেভ হবে)
        return file_path;

    } catch (error) {
        console.error(Upload Error, error);
        throw error;
    }
};
এই আর্কিটেকচারের সুবিধা

Zero Backend Load ইউজার 1GB সাইজের ফাইল আপলোড করলেও আপনার FastAPI এবং Cloud Run-এর মেমোরি 0% ব্যবহৃত হবে।

Speed সরাসরি Cloudflare-এর গ্লোবাল এজ নেটওয়ার্কে ফাইল আপলোড হওয়ায় স্পিড অনেক বেশি পাওয়া যাবে।