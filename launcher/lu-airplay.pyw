"""Startpunkt für Lu AirPlay Receiver:  python launcher/lu-airplay.pyw"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from luairplay.app import main  # noqa: E402

main()
