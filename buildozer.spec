[app]
title = MS Fetcher
package.name = msfetcher
package.domain = org.itzaura1.msfetcher

source.dir = .
source.include_exts = py,png,jpg,kv,txt,json

version = 1.0.0

requirements = python3,kivy,requests,pyyaml,urllib3,cryptography,pysocks

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1