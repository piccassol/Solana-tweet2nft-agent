
- Solana-tweet2nft-agent

![image](https://github.com/user-attachments/assets/5ec2602e-e997-47eb-ae77-a2e89cc43572)

This is an AI agent that takes a tweet ID as input, fetches the image from the tweet (assuming it's a photo), downloads it, uploads the image and metadata to IPFS (assuming a local IPFS node is running), and mints it as an NFT on Solana's devnet using the Metaplex Token Metadata program.

 - Solana Tweet NFT Agent

This Python-based agent scrapes images from tweets on X (via Nitter, without an API key), uploads them to NFT.Storage, and mints them as NFTs on the Solana blockchain (devnet by default) using the Metaplex Token Metadata program.

Disclaimer: For educational purposes only. Scraping X may violate its terms of service—use at your own risk. Minting NFTs incurs small SOL fees (even on devnet). Requires a free NFT.Storage API key and a Solana wallet with devnet SOL.

- Prerequisites

- Python 3.8+
- Solana CLI (`solana --version`)
- A Solana wallet keypair (generate with `solana-keygen new`)
- NFT.Storage API key (free at https://nft.storage/)
- Devnet SOL (get via `solana airdrop 2`)

Setup

1. Clone the repository;
   ```bash
   git clone https://github.com/yourusername/solana-tweet-nft-agent.git
   cd solana-tweet-nft-agent

2. Instal Dependencies:
   pip install -r requirements.txt

  

3. Configure environment variables:
Copy .env.example to .env and fill in:cp .env.example .env

edit .env: 
NFT_STORAGE_KEY=your_nft_storage_api_key
SOLANA_KEYPAIR=~/.config/solana/id.json
SOLANA_RPC=https://api.devnet.solana.com
  
4. Run the Agent:
5.  python main.py --user elonmusk

How It Works

Scraping: Uses Nitter to fetch tweets with images from a specified user, avoiding X's API key requirement.
Image Upload: Downloads tweet images and uploads them to NFT.Storage, generating an IPFS CID.
Metadata Creation: Creates JSON metadata (name, description, image CID, tweet URL) and uploads it to NFT.Storage.
NFT Minting: Uses Solana’s Python libraries (solana, solders) to create a token mint, associated token account, and Metaplex metadata, minting a single NFT per image.
