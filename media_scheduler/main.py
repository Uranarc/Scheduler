"""Application entry point for the media scheduler GUI."""

from media_scheduler.db.schema import init_db
from media_scheduler.gui.app import App


if __name__ == '__main__':
    init_db()
    App().mainloop()


