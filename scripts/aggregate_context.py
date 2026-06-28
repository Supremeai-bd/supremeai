import os
import glob
import sys
import io

# Windows console encoding error bypass (Unicode/Emojis support)
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# বাংলা মন্তব্য: মডিউলার XML ফাইলগুলো যুক্ত করে রানটাইমে সিঙ্গেল কনটেক্সট ফাইল তৈরি করা
def build_god_context(source_dir="context_modules", output_file="supremeai_god_context.xml"):
    os.makedirs(source_dir, exist_ok=True)
    xml_files = glob.glob(os.path.join(source_dir, "*.xml"))
    
    if not xml_files:
        print(f"⚠️ {source_dir} ডিরেক্টরিতে কোনো XML ফাইল পাওয়া যায়নি!")
        return

    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        outfile.write('<supreme_ai_context>\n')
        
        for file in xml_files:
            filename = os.path.basename(file)
            tag_name = filename.replace('.xml', '')
            
            outfile.write(f'  \n')
            outfile.write(f'  <{tag_name}>\n')
            
            with open(file, "r", encoding="utf-8") as infile:
                content = infile.read()
                # বাংলা মন্তব্য: ফাইলের ভেতরের XML হেডার মুছে ফেলা হচ্ছে
                content = content.replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()
                outfile.write(f"    {content}\n")
                
            outfile.write(f'  </{tag_name}>\n\n')
            
        outfile.write('</supreme_ai_context>\n')
        
    print(f"✅ সফলভাবে {len(xml_files)}টি মডিউল যুক্ত করে {output_file} তৈরি করা হয়েছে।")

if __name__ == "__main__":
    build_god_context()
