# IMF Creator

**This project is still a work-in-progress.**

A program to create IMF music used by several classic ID and Apogee games such as Wolfenstein 3D and Commander Keen.

## Getting Started

### Prerequisites

You need Python 3.6 or higher to run this.

### Installing

Clone or download this repository.

#### Windows
While running the command prompt as system administrator:

    pip install -r requirements.txt

##### PyAudio

On Windows, `pip` can fail to install PyAudio depending on what version of Python you're using.

To fix this, run the following as system administrator:

    pip install pipwin
    pipwin install pyaudio

#### Linux
On Linux you will need to install some dependencies to run this.

##### Ubuntu / Debian
```bash
sudo apt install tix-dev python3-tk python3-pyaudio python3-watchdog
```

## License

This project is dual licensed under the MIT License and GPL 3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements
* Adam Nielsen (Malvineous) for his [PyOPL](https://github.com/Malvineous/pyopl) library.
* [FreeDoom](https://github.com/freedoom/freedoom) for its GENMIDI.OP2 file.
* [Kenney.nl](https://opengameart.org/content/game-icons) for the button icons. (CC0 License)
