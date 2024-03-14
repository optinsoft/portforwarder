from PyMultiInstaller import make_all_installer

if __name__ == '__main__':
    make_all_installer([
        [
            'portforwarder.py',
            '--noconfirm'
        ]
    ])
