import os
import json
import requests
from bs4 import BeautifulSoup
from nftstorage import NFTStorageAPIClient
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction as TransactionInstruction
from solders.system_program import CreateAccountParams, create_account
from solders.sysvar import RENT as SYSVAR_RENT_PUBKEY
from solana.rpc.api import Client
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import InitializeMintParams, initialize_mint, MintToParams, mint_to, SetAuthorityParams, set_authority, AuthorityType
from spl.associated_token_account import get_associated_token_address, create_associated_token_account
from borsh_construct import CStruct, String, Bool, U8, U16, U64, Vec, Option, FixedBytes
from argparse import ArgumentParser

METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3y9kZ1bezhbuwKqw")

bytes32 = FixedBytes(32)

creator_struct = CStruct(
    "address" / bytes32,
    "verified" / Bool,
    "share" / U8
)

collection_struct = CStruct(
    "verified" / Bool,
    "key" / bytes32
)

uses_struct = CStruct(
    "use_method" / U8,
    "remaining" / U64,
    "total" / U64
)

data_v2_struct = CStruct(
    "name" / String,
    "symbol" / String,
    "uri" / String,
    "seller_fee_basis_points" / U16,
    "creators" / Option(Vec(creator_struct)),
    "collection" / Option(collection_struct),
    "uses" / Option(uses_struct)
)

create_metadata_accounts_v3_data_struct = CStruct(
    "data" / data_v2_struct,
    "is_mutable" / Bool,
    "collection_details" / Option(U8)  # None for v1 NFTs
)

def scrape_tweets(user):
    url = f"https://nitter.net/search?f=tweets&q=from:{user} filter:images"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to load page: {response.status_code}")
    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.find_all('div', class_='timeline-item')
    tweets = []
    for item in items:
        img = item.find('img', class_='image-thumbnail')
        if img:
            thumb_src = img['src']
            orig_src = thumb_src.replace('name=small', 'name=orig')
            full_image = 'https://nitter.net' + orig_src
            text_div = item.find('div', class_='tweet-content')
            text = text_div.text if text_div else ''
            link = item.find('a', class_='tweet-link')
            if link:
                tweet_id = link['href'].split('/')[-1].split('#')[0]
                tweet_url = f"https://x.com/{user}/status/{tweet_id}"
                tweets.append({'image_url': full_image, 'text': text, 'tweet_url': tweet_url})
    return tweets

def download_image(url, path):
    resp = requests.get(url)
    if resp.status_code == 200:
        with open(path, 'wb') as f:
            f.write(resp.content)
    else:
        raise Exception(f"Failed to download image: {resp.status_code}")

def upload_image(client, path):
    with open(path, 'rb') as f:
        response = client.store(f)
    return response['value']['cid']

def create_metadata_json(name, description, image_cid, external_url):
    metadata = {
        "name": name,
        "description": description,
        "image": f"https://nftstorage.link/ipfs/{image_cid}",
        "external_url": external_url,
        "attributes": [{"trait_type": "source", "value": "tweet"}]
    }
    temp_file = 'temp_metadata.json'
    with open(temp_file, 'w') as f:
        json.dump(metadata, f)
    return temp_file

def upload_metadata(client, path):
    with open(path, 'rb') as f:
        response = client.store(f)
    os.remove(path)
    return response['value']['cid']

def create_metadata_instruction(metadata_pda, mint, mint_authority, payer, update_authority, data_v2, is_mutable):
    serialized_data = bytes([33]) + create_metadata_accounts_v3_data_struct.build({
        "data": data_v2,
        "is_mutable": is_mutable,
        "collection_details": None
    })
    keys = [
        {"pubkey": metadata_pda, "is_signer": False, "is_writable": True},
        {"pubkey": mint, "is_signer": False, "is_writable": False},
        {"pubkey": mint_authority, "is_signer": True, "is_writable": False},
        {"pubkey": payer, "is_signer": True, "is_writable": False},
        {"pubkey": update_authority, "is_signer": False, "is_writable": False},
        {"pubkey": Pubkey.from_string("11111111111111111111111111111111"), "is_signer": False, "is_writable": False},
        {"pubkey": SYSVAR_RENT_PUBKEY, "is_signer": False, "is_writable": False},
    ]
    return TransactionInstruction(
        keys=[AccountMeta(pubkey=key["pubkey"], is_signer=key["is_signer"], is_writable=key["is_writable"]) for key in keys],
        program_id=METADATA_PROGRAM_ID,
        data=serialized_data
    )

def mint_nft(solana_client, payer, uri, name, symbol):
    mint_key = Keypair()
    mint_pubkey = mint_key.pubkey
    lamports = solana_client.get_minimum_balance_for_rent_exemption(82).value
    create_ix = create_account(CreateAccountParams(
        from_pubkey=payer.pubkey,
        new_account_pubkey=mint_pubkey,
        lamports=lamports,
        space=82,
        program_id=TOKEN_PROGRAM_ID
    ))
    init_ix = initialize_mint(InitializeMintParams(
        decimals=0,
        mint=mint_pubkey,
        mint_authority=payer.pubkey,
        program_id=TOKEN_PROGRAM_ID
    ))
    ata = get_associated_token_address(payer.pubkey, mint_pubkey)
    create_ata_ix = create_associated_token_account(payer.pubkey, payer.pubkey, mint_pubkey)
    mint_ix = mint_to(MintToParams(
        program_id=TOKEN_PROGRAM_ID,
        dest=ata,
        mint=mint_pubkey,
        authority=payer.pubkey,
        amount=1
    ))
    disable_ix = set_authority(SetAuthorityParams(
        program_id=TOKEN_PROGRAM_ID,
        account=mint_pubkey,
        authority=AuthorityType.MintTokens,
        current_authority=payer.pubkey,
        new_authority=None
    ))
    metadata_pda, _ = Pubkey.find_program_address(
        [b"metadata", bytes(METADATA_PROGRAM_ID), bytes(mint_pubkey)],
        METADATA_PROGRAM_ID
    )
    data_v2 = {
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "seller_fee_basis_points": 500,
        "creators": [{"address": bytes(payer.pubkey), "verified": True, "share": 100}],
        "collection": None,
        "uses": None
    }
    metadata_ix = create_metadata_instruction(metadata_pda, mint_pubkey, payer.pubkey, payer.pubkey, payer.pubkey, data_v2, True)
    tx = Transaction()
    tx.add(create_ix, init_ix, create_ata_ix, mint_ix, disable_ix, metadata_ix)
    solana_client.send_transaction(tx, payer, mint_key)
    return mint_pubkey

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--user", required=True, help="X username to scrape tweets from")
    args = parser.parse_args()

    nft_storage_key = os.environ.get("NFT_STORAGE_KEY")
    if not nft_storage_key:
        raise ValueError("NFT_STORAGE_KEY environment variable not set")

    keypair_file = os.environ.get("SOLANA_KEYPAIR")
    if not keypair_file:
        raise ValueError("SOLANA_KEYPAIR environment variable not set")

    rpc = os.environ.get("SOLANA_RPC", "https://api.devnet.solana.com")

    with open(keypair_file) as f:
        secret_key = json.load(f)

    payer = Keypair.from_secret_key(bytes(secret_key))

    solana_client = Client(rpc)

    nft_client = NFTStorageAPIClient(api_key=nft_storage_key)

    tweets = scrape_tweets(args.user)

    for i, tweet in enumerate(tweets[:5]):  # Limit to 5 for demo
        image_path = f"tweet_image_{i}.jpg"
        download_image(tweet['image_url'], image_path)
        image_cid = upload_image(nft_client, image_path)
        description = f"{tweet['text']}\nMinted from tweet: {tweet['tweet_url']}"
        metadata_path = create_metadata_json("Tweet NFT", description, image_cid, tweet['tweet_url'])
        metadata_cid = upload_metadata(nft_client, metadata_path)
        uri = f"https://nftstorage.link/ipfs/{metadata_cid}"
        mint_pubkey = mint_nft(solana_client, payer, uri, "Tweet NFT", "TNFT")
        print(f"Minted NFT for tweet {tweet['tweet_url']}: {mint_pubkey}")
        os.remove(image_path)
