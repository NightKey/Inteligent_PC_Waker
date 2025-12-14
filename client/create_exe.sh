if ! [ -d venv ]
then
    echo "venv doesn't exist, creating venv."
    python3 -m virtualenv venv
fi

if ! [ -d venv ]
then
    echo "Installing python virtualenv"
    source install.sh "$@"
    exit 0
fi

#If not in venv, activate venv.
if [[ "$VIRTUAL_ENV" = "" ]]
then
    source venv/bin/activate
fi

pip install -r dependencies.txt --upgrade
pip install pyinstaller
pyinstaller -w -n "Waker Client" -F waker_client.py