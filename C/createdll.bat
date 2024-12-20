@echo off
SET code=%~dp0

gcc -shared -o %code%/arp.dll -fPIC %code%/arp.c -lws2_32 -liphlpapi
echo .dll file created
