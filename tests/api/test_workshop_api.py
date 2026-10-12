def test_post_car_returns_201_and_json(client):
    payload = {
        "make": "Ford",
        "model": "Fiesta",
        "year": 2018,
        "color": "Black",
    }
    response = client.post("/api/cars", json=payload)
    assert response.status_code == 201
    car = response.json()
    assert car["id"] > 0
    assert car["make"] == "Ford"
    assert car["model"] == "Fiesta"
    assert response.headers["location"] == f"/api/cars/{car['id']}"


def test_invalid_year_is_not_saved(client):
    payload = {
        "make": "Ford",
        "model": "Fiesta",
        "year": 1800,
        "color": "Black",
    }
    response = client.post("/api/cars", json=payload)
    assert response.status_code == 422

    listed = client.get("/api/cars")
    assert listed.status_code == 200
    assert listed.json() == []
