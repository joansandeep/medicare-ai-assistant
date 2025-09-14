# IPFS Configuration for Free Deployment
import requests
import os

class IPFSManager:
    def __init__(self):
        # Free IPFS services
        self.pinata_api_key = os.environ.get('PINATA_API_KEY')
        self.pinata_secret = os.environ.get('PINATA_SECRET')
        
        # Fallback to public gateways
        self.gateways = [
            "https://ipfs.io/ipfs/",
            "https://gateway.pinata.cloud/ipfs/",
            "https://cloudflare-ipfs.com/ipfs/",
            "https://dweb.link/ipfs/"
        ]
    
    def upload_to_pinata(self, file_content, filename):
        """Upload file to Pinata (Free IPFS pinning service)"""
        if not self.pinata_api_key:
            raise Exception("Pinata API key not configured")
        
        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        
        headers = {
            'pinata_api_key': self.pinata_api_key,
            'pinata_secret_api_key': self.pinata_secret
        }
        
        files = {
            'file': (filename, file_content)
        }
        
        response = requests.post(url, files=files, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result['IpfsHash']
        else:
            raise Exception(f"Pinata upload failed: {response.text}")
    
    def get_file_url(self, cid):
        """Get file URL from IPFS gateway"""
        return f"{self.gateways[0]}{cid}"
    
    def download_file(self, cid):
        """Download file from IPFS"""
        for gateway in self.gateways:
            try:
                url = f"{gateway}{cid}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    return response.content
            except:
                continue
        raise Exception("Failed to download from all gateways")

# Usage for free deployment
ipfs_manager = IPFSManager()