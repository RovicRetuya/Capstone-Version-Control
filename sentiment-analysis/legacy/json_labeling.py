import os
import json
import time
from tqdm import tqdm
import logging
import argparse
import pyperclip
import sys
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('classification_json.log'),
        logging.StreamHandler()
    ]
)

def extract_sentiment(label_text):
    """Extract just the NEG/NEU/POS from potentially longer label text."""
    label_text = label_text.upper()
    if "POS" in label_text:
        return "POS"
    elif "NEG" in label_text:
        return "NEG"
    elif "NEU" in label_text:
        return "NEU"
    return None

def load_json(json_path):
    """Load JSON data from a file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Error loading JSON: {str(e)}")
        return []

def save_json(json_path, data):
    """Save JSON data to a file."""
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving JSON: {str(e)}")

def flatten_comments(data):
    """
    Flatten all non-empty comments into a list of (index, comment_text).
    Also keep track of where they came from: (outer_idx, comment_idx).
    """
    flattened = []
    counter = 0
    for outer_idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        comments = item.get("comments", [])
        if not isinstance(comments, list):
            continue
        for comment_idx, cmt in enumerate(comments):
            text = cmt.get("content", "").strip()
            if text:  # only consider non-empty
                # If the comment already has a 'sentiment' key, skip if labeled
                if "sentiment" not in cmt or cmt["sentiment"] in ("<NEG/NEU/POS>", None, ""):
                    flattened.append({
                        "global_index": counter,
                        "outer_idx": outer_idx,
                        "comment_idx": comment_idx,
                        "content": text
                    })
                    counter += 1
    return flattened

def restore_comments(data, flattened):
    """
    Write back each labeled comment's sentiment into the original data structure.
    """
    for item in flattened:
        o_idx = item["outer_idx"]
        c_idx = item["comment_idx"]
        sentiment = item["sentiment"]
        data[o_idx]["comments"][c_idx]["sentiment"] = sentiment

def get_user_input_immediate(chunk, all_items, auto_copy=True):
    """
    Immediately parse lines as user enters them.
    Once a line is correctly parsed, update the classification.
    If the same index appears multiple times, the last one will overwrite the previous.
    """
    # Build the prompt text
    prompt = (
        "You are a Vietnamese sentiment classifier. Classify each comment as one of <NEG>, <NEU>, or <POS>.\n"
        "Reply in the format: INDEX: <NEG/NEU/POS>\n\n"
    )
    for item in chunk:
        prompt += f"Comment {item['global_index']}: {item['content']}\n"

    print("\n=== PROMPT TO COPY (if needed) ===")
    print(prompt)
    print("===================================")
    
    if auto_copy:
        try:
            pyperclip.copy(prompt)
            print("\nPrompt copied to clipboard!")
        except:
            print("\nFailed to copy to clipboard")

    print("\nEnter each classification line in the format 'INDEX: <NEG/NEU/POS>'.")
    print("Type 'done' when finished, or 'exit' to abort this chunk.\n")
    
    needed_indices = {it["global_index"] for it in chunk}
    new_labels = {}

    while needed_indices:
        user_line = input("Classification > ").strip()
        if user_line.lower() == 'done':
            if needed_indices:
                print(f"Still missing indices: {needed_indices}")
                continue
            else:
                break
        elif user_line.lower() == 'exit':
            print("Aborting this chunk...")
            break
        
        parts = user_line.split(":")
        if len(parts) == 2:
            idx_str, label = parts[0].strip(), parts[1].strip()
            sentiment_type = extract_sentiment(label)
            if sentiment_type:
                # Attempt to parse the integer index
                idx_str = idx_str.replace('Comment', '').strip()
                try:
                    real_idx = int(idx_str)
                    if real_idx in needed_indices:
                        new_labels[real_idx] = f"<{sentiment_type}>"
                    else:
                        print(f"Index {real_idx} not in current chunk.")
                except ValueError:
                    print(f"Could not parse index '{idx_str}', please try again.")
            else:
                print("Invalid sentiment. Must contain NEG, NEU, or POS.")
        else:
            print("Invalid format. Use 'INDEX: <NEG/NEU/POS>'.")
        
        for assigned_idx in list(needed_indices):
            if assigned_idx in new_labels:
                needed_indices.remove(assigned_idx)

    # Apply all new labels
    for k, v in new_labels.items():
        # find item in chunk with global_index = k
        for it in chunk:
            if it["global_index"] == k:
                it["sentiment"] = v

    return len(new_labels)

def manual_classify(flattened, chunk_size=10, auto_copy=True):
    """Manual classification logic."""
    idx = 0
    with tqdm(total=len(flattened), desc="Processing comments") as pbar:
        while idx < len(flattened):
            chunk = flattened[idx:idx+chunk_size]
            processed = get_user_input_immediate(chunk, flattened, auto_copy=auto_copy)
            pbar.update(len(chunk))
            logging.info(f"Processed {processed}/{len(chunk)} comments in chunk")
            idx += chunk_size

def automatic_classify(flattened, chunk_size=10):
    """Automatic classification logic using openai (if needed)."""
    from openai import OpenAI
    client = OpenAI(api_key="YOUR_API_KEY")

    idx = 0
    with tqdm(total=len(flattened), desc="Processing comments") as pbar:
        while idx < len(flattened):
            chunk = flattened[idx:idx+chunk_size]
            prompt = (
                "You are a Vietnamese sentiment classifier. Classify each comment as one of <NEG>, <NEU>, or <POS>. "
                "Reply in the format: INDEX: <NEG/NEU/POS>\n\n"
            )
            for it in chunk:
                prompt += f"Comment {it['global_index']}: {it['content']}\n"
            prompt += "\nReply with lines in the form:\nINDEX: <NEG/NEU/POS>\n"

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0
                )
                answer = response.choices[0].message.content.strip().splitlines()
                processed = 0

                for line in answer:
                    parts = line.split(":")
                    if len(parts) == 2:
                        idx_str, label = parts[0].strip(), parts[1].strip()
                        sentiment_type = extract_sentiment(label)
                        if sentiment_type:
                            try:
                                real_idx = int(idx_str.replace("Comment", "").strip())
                                # find item in chunk with global_index == real_idx
                                for it in chunk:
                                    if it["global_index"] == real_idx:
                                        it["sentiment"] = f"<{sentiment_type}>"
                                        processed += 1
                                        break
                            except ValueError:
                                logging.error(f"Error parsing index in line {line}")
            
            except Exception as e:
                logging.error(f"API error: {str(e)}")
                time.sleep(5)
                continue

            pbar.update(len(chunk))
            logging.info(f"Processed {processed}/{len(chunk)} comments in chunk")
            idx += chunk_size

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--manual", action="store_true", help="Manual mode - copy/paste to GPT")
    parser.add_argument("-c", "--chunk_size", type=int, default=20, help="Chunk size for processing")
    parser.add_argument("-f", "--file", type=str, default='shopee_genshinimpact.json', help="Path to JSON file")
    parser.add_argument("--no-auto-copy", action="store_true", help="Disable auto-copy to clipboard")
    args = parser.parse_args()

    # Load data
    json_path = args.file
    logging.info(f"Loading JSON from {json_path}")
    data = load_json(json_path)

    # Flatten relevant comments
    flattened = flatten_comments(data)
    if not flattened:
        logging.info("No unlabeled, non-empty comments found.")
        return

    # Backup original
    backup_path = json_path.replace(".json", "_backup.json")
    logging.info(f"Backing up to {backup_path}")
    save_json(backup_path, data)

    # Classify
    if args.manual:
        manual_classify(flattened, chunk_size=args.chunk_size, auto_copy=not args.no_auto_copy)
    else:
        automatic_classify(flattened, chunk_size=args.chunk_size)

    # Write back results
    restore_comments(data, flattened)
    save_json(json_path, data)
    logging.info("Classification completed and saved.")

if __name__ == "__main__":
    main()