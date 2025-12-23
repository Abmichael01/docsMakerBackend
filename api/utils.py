import random
import string

def obfuscate_answer(text: str) -> str:
    """
    Obfuscates an answer using a custom scheme:
    1. Normalizes text (lowercase, no spaces).
    2. Interleaves character indices with the characters.
    3. Adds random salt at the beginning and end.
    """
    if not text:
        return ""
    
    # Normalize
    clean_text = "".join(text.split()).lower()
    
    # Interleave indices: Abayomi -> 0a1b2a3y4o5m6i
    interleaved = ""
    for i, char in enumerate(clean_text):
        interleaved += f"{i}{char}"
    
    # Add random padding (junk)
    prefix_len = random.randint(5, 10)
    suffix_len = random.randint(5, 10)
    
    prefix = "".join(random.choices(string.ascii_letters + string.digits, k=prefix_len))
    suffix = "".join(random.choices(string.ascii_letters + string.digits, k=suffix_len))
    
    # We use a special marker to delineate the content if we wanted to decode, 
    # but since we only compare, we don't necessarily need it IF we store the salt.
    # Actually, if we use random salt, we CANNOT easily re-obfuscate for comparison 
    # UNLESS we store the salt or use a deterministic approach.
    
    # Let's use a DETERMINISTIC salt based on the text itself or a fixed key 
    # so we can re-create the exact obfuscated string for comparison.
    # OR, we don't use random salt for the stored version if we want simple equality check.
    
    # User said: "you wirt ea lot of bnc od text the u do somethiung to the cahrs of the letter"
    # To make it "hacker proof" but "verifiable", I'll use a fixed but complex "junk" pattern.
    
    JUNK_PREFIX = "sh8rp"
    JUNK_SUFFIX = "t00lz"
    
    return f"{JUNK_PREFIX}{interleaved}{JUNK_SUFFIX}"

def verify_answer(input_text: str, stored_obfuscated: str) -> bool:
    """
    Verifies if the input matches the stored obfuscated version.
    """
    if not input_text or not stored_obfuscated:
        return False
        
    return obfuscate_answer(input_text) == stored_obfuscated
