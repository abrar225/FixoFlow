"""Download only the pinned, MIT-licensed CPU model at build time."""
from pathlib import Path
import hashlib
import json
import urllib.request
import argparse

REPO='Systran/faster-whisper-base.en'
REVISION='3d3d5dee26484f91867d81cb899cfcf72b96be6c'
FILES=('config.json','model.bin','tokenizer.json','vocabulary.txt','README.md')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for name in FILES:
        destination=args.output/name
        temporary=destination.with_suffix(destination.suffix+'.download')
        try:
            with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}',timeout=120) as response,temporary.open('wb') as output:
                while block:=response.read(1024*1024):output.write(block)
            if not temporary.stat().st_size:raise RuntimeError('Empty model file: '+name)
            temporary.replace(destination)
        finally:temporary.unlink(missing_ok=True)
    manifest={'repository':REPO,'revision':REVISION,'license':'MIT','files':{name:hashlib.sha256((args.output/name).read_bytes()).hexdigest() for name in FILES}}
    (args.output/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
