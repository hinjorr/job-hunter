from jobhunter import notify


def test_chunks_respect_limit_and_keep_all_text():
    text = "".join(f"- line {i} https://example.com/job/{i}\n" for i in range(200)) + "x" * 5000 + "\n"
    parts = notify._chunks(text, 1900)
    assert all(len(p) <= 1900 for p in parts)
    assert "".join(parts) == text


def test_discord_posts_each_chunk(monkeypatch):
    sent = []

    class Resp:
        def raise_for_status(self):
            pass

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    monkeypatch.setattr(notify.requests, "post", lambda url, json, timeout: sent.append(json) or Resp())
    notify.send_discord("a\n" * 3000)
    assert len(sent) == 4 and all(len(m["content"]) <= 1900 for m in sent)
    assert sent[0]["allowed_mentions"] == {"parse": []}


def test_send_all_survives_a_failing_channel(monkeypatch):
    calls = []

    def boom(text):
        raise RuntimeError("network down")

    monkeypatch.setattr(notify, "send_telegram", boom)
    monkeypatch.setattr(notify, "send_discord", lambda text: calls.append(text))
    notify.send_all("digest")
    assert calls == ["digest"]
