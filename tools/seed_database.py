import os
import sys
import importlib.util
import hashlib

# Add project root to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from tools.local_search_rag import LocalSearchRAG

def seed_all():
    print("Initializing LocalSearchRAG...")
    rag = LocalSearchRAG()
    
    seed_data_dir = os.path.join(base_dir, "tools", "seed_data")
    if not os.path.exists(seed_data_dir):
        print(f"Error: seed_data directory not found at {seed_data_dir}")
        return

    print("Scanning seed modules...")
    ids = []
    documents = []
    metadatas = []
    
    for filename in os.listdir(seed_data_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "helpers.py"]:
            module_name = filename[:-3]
            module_path = os.path.join(seed_data_dir, filename)
            
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(f"tools.seed_data.{module_name}", module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # Need to add parent folder to sys.path so relative imports in seed files work
                sys.path.insert(0, seed_data_dir)
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    print(f"Failed to load {module_name}: {e}")
                    continue
                finally:
                    sys.path.pop(0)
                
                # Find dictionaries in the module
                for attr_name in dir(module):
                    if attr_name.isupper():
                        attr_val = getattr(module, attr_name)
                        if isinstance(attr_val, dict):
                            print(f"Processing dict '{attr_name}' in {module_name}...")
                            for key, item in attr_val.items():
                                if not isinstance(item, dict):
                                    continue
                                
                                # Format document string for ChromaDB
                                doc_title = item.get("title", item.get("name", item.get("error_message", key)))
                                doc_content = f"Title: {doc_title}\n"
                                if "cause" in item:
                                    doc_content += f"Cause: {item['cause']}\n"
                                if "fix" in item:
                                    doc_content += f"Solution/Fix: {item['fix']}\n"
                                if "description" in item:
                                    doc_content += f"Description: {item['description']}\n"
                                if "when_to_use" in item:
                                    doc_content += f"When to use: {item['when_to_use']}\n"
                                if "code_example" in item:
                                    doc_content += f"Code Example:\n{item['code_example']}\n"
                                if "do" in item:
                                    doc_content += f"DO: {', '.join(item['do']) if isinstance(item['do'], list) else item['do']}\n"
                                if "dont" in item:
                                    doc_content += f"DONT: {', '.join(item['dont']) if isinstance(item['dont'], list) else item['dont']}\n"
                                if "content" in item:
                                    doc_content += f"Content: {item['content']}\n"
                                if "solutions" in item:
                                    doc_content += f"Solutions: {', '.join(item['solutions']) if isinstance(item['solutions'], list) else item['solutions']}\n"
                                
                                doc_id = hashlib.md5(f"{module_name}_{key}".encode('utf-8')).hexdigest()
                                ids.append(doc_id)
                                documents.append(doc_content)
                                metadatas.append({
                                    "source": "supremeai_1.0_seed",
                                    "module": module_name,
                                    "key": key,
                                    "title": doc_title[:100],
                                    "language": item.get("language", "generic"),
                                    "framework": item.get("framework", "generic"),
                                })

    if ids:
        print(f"Upserting {len(ids)} expert knowledge patterns to ChromaDB...")
        try:
            rag.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            print("Successfully seeded all SupremeAI 1.0 expert knowledge!")
        except Exception as e:
            print(f"ChromaDB Upsert failed: {e}. Writing to fallback index.")
            # Writing to fallback json index
            for idx, doc_id in enumerate(ids):
                rag._index[doc_id] = [metadatas[idx]["title"], documents[idx]]
            rag._store_search("expert_seed", {})
            print("Successfully seeded to fallback index file.")
    else:
        print("No seed data found to import.")

if __name__ == "__main__":
    seed_all()
