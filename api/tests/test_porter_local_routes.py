from uuid import uuid4


async def _route_test_user(db_session):
    suffix = uuid4().hex
    user, _ = await db_session.get_or_create_user_by_provider_id(
        f"porter-route-user-{suffix}"
    )
    org, _ = await db_session.get_or_create_organization_by_provider_id(
        org_provider_id=f"porter-route-org-{suffix}",
        user_id=user.id,
    )
    await db_session.add_user_to_organization(user.id, org.id)
    await db_session.update_user_selected_organization(user.id, org.id)
    user.selected_organization_id = org.id
    return user


async def test_porter_local_web_call_simulation_route(test_client_factory, db_session):
    user = await _route_test_user(db_session)

    async with test_client_factory(user) as client:
        response = await client.post(
            "/api/v1/porter-local/web-call-simulations",
            json={
                "user_turns": [
                    "Yes, I have a minute.",
                    "Call me later tomorrow.",
                ],
                "synthesize_audio": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["disposition"] == "callback_requested"
    assert payload["telephony_enabled"] is False
    assert payload["crm_sync_enabled"] is False
    assert payload["transcript"]


async def test_porter_local_review_routes(test_client_factory, db_session):
    user = await _route_test_user(db_session)

    async with test_client_factory(user) as client:
        create_response = await client.post(
            "/api/v1/porter-local/web-call-simulations",
            json={
                "user_turns": ["What are your rates?"],
                "synthesize_audio": False,
            },
        )
        call_session_id = create_response.json()["summary"]["call_session_id"]

        list_response = await client.get("/api/v1/porter-local/call-sessions")
        detail_response = await client.get(
            f"/api/v1/porter-local/call-sessions/{call_session_id}"
        )

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert any(
        row["id"] == call_session_id for row in list_response.json()["sessions"]
    )
    detail = detail_response.json()["session"]
    assert detail["id"] == call_session_id
    assert detail["transcript"]
    assert detail["outcome"]


async def test_porter_voice_runtime_routes(test_client_factory, db_session):
    user = await _route_test_user(db_session)

    async with test_client_factory(user) as client:
        readiness_response = await client.get("/api/v1/porter-local/voice-runtime/readiness")
        prewarm_response = await client.post(
            "/api/v1/porter-local/voice-runtime/prewarm",
            json={"script_names": ["opener"]},
        )

    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["recommended_target_ms"] == 500
    assert {component["name"] for component in readiness["components"]} == {
        "stt",
        "tts",
        "llm",
    }

    assert prewarm_response.status_code == 200
    prewarm = prewarm_response.json()
    assert prewarm["warmed_count"] == 1
    assert prewarm["scripts"][0]["script_name"] == "opener"
