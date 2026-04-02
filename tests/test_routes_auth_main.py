from interview_simulator.extensions import db
from interview_simulator.models import User


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_register_login_logout_flow(client, app):
    response = client.post(
        "/register",
        data={
            "name": "Route User",
            "email": "route@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        assert User.query.filter_by(email="route@example.com").first() is not None

    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200

    response = client.post(
        "/login",
        data={"email": "route@example.com", "password": "secret123"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_register_rejects_short_password(client):
    response = client.post(
        "/register",
        data={
            "name": "A",
            "email": "short@example.com",
            "password": "123",
            "confirm_password": "123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Password must be at least 6 characters long" in response.data
