from air3d_app import app, socketio


if __name__ == "__main__":
    socketio.run(app, debug=True)
