"""Download the latest object under a GCS prefix to a local CSV.
Usage: python fetch_gcs.py gs://bucket/prefix/ out.csv   (needs `pip install google-cloud-storage` + gcloud auth application-default login)
Also prints the object's updated timestamp so you can prove WHICH run produced it."""
import sys
from google.cloud import storage
uri, dst = sys.argv[1], sys.argv[2]
bucket, _, prefix = uri[5:].partition("/")
blobs = sorted(storage.Client().list_blobs(bucket, prefix=prefix), key=lambda b: b.updated)
blobs = [b for b in blobs if not b.name.endswith("/")]
if not blobs: sys.exit(f"no objects under {uri}")
b = blobs[-1]; b.download_to_filename(dst)
print(f"{b.name} updated={b.updated.isoformat()} size={b.size} -> {dst}")
