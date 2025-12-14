echo $'\033]30;Waker Client\007'

#If venv doesn't exist, create venv and install dependencies.
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

pip install --upgrade --extra-index-url https://PySimpleGUI.net/install PySimpleGUI
echo "Starting"
python waker_client.py
deactivate
