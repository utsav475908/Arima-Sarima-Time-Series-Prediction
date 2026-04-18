
# Using sliding window technique

def get_token_chunks(tokens, chunk_size, overlap):
    chunks = []
    step = chunk_size - overlap

    for i in range(0, len(tokens), step):
        chunk = tokens[i: i + chunk_size]
        if len(chunk) < chunk_size:
            break
        chunks.append(chunk)
    return chunks


tokens = ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]
chunk_size = 4
overlap = 2

print(get_token_chunks(tokens, chunk_size, overlap))
