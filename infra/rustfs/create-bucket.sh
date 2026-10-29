#!/bin/sh
set -eu

: "${RUSTFS_BUCKET:?set RUSTFS_BUCKET}"

if aws s3api head-bucket --bucket "$RUSTFS_BUCKET" >/dev/null 2>&1; then
  echo "RustFS bucket already exists: $RUSTFS_BUCKET"
else
  aws s3 mb "s3://$RUSTFS_BUCKET" >/dev/null
  echo "Created RustFS bucket: $RUSTFS_BUCKET"
fi

aws s3api head-bucket --bucket "$RUSTFS_BUCKET" >/dev/null
echo "RustFS bucket is ready: $RUSTFS_BUCKET"
