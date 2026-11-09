from bailoteca.models import Candidate
from bailoteca.sources.filters import is_noise


def _c(url):
    return Candidate("X", url, None, "serpapi")


def test_drops_directory_domains_and_subdomains():
    assert is_noise(_c("https://www.superprof.cl/salsa"))
    assert is_noise(_c("https://blog.superprof.cl/x"))
    assert is_noise(_c("https://WWW.SUPERPROF.CL/x"))
    assert is_noise(_c("https://open.spotify.com/album/1"))


def test_keeps_real_academy_hosts():
    assert not is_noise(_c("https://asyouwish.cl/"))
    assert not is_noise(_c("https://www.instagram.com/academiatimbalero/"))
    assert not is_noise(_c("https://www.facebook.com/mueveteontour/"))


def test_drops_content_paths_everywhere():
    assert is_noise(_c("https://www.facebook.com/mueveteontour/videos/x/"))
    assert is_noise(_c("https://www.facebook.com/x/events/1/"))
    assert is_noise(_c("https://academia.cl/permalink/123"))


def test_drops_facebook_group_posts_but_keeps_group_home():
    assert is_noise(_c("https://www.facebook.com/groups/146838812091667/posts/1/"))
    assert not is_noise(_c("https://www.facebook.com/groups/146838812091667/"))


def test_drops_instagram_non_profile_paths():
    for url in (
        "https://www.instagram.com/popular/clases-de-salsa/",
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/ABC123/",
        "https://www.instagram.com/stories/x/1/",
    ):
        assert is_noise(_c(url)), url


def test_malformed_or_empty_url_is_kept():
    assert not is_noise(_c(""))
    assert not is_noise(_c("no-es-una-url"))


def test_drops_measured_directory_and_listicle_pages():
    assert is_noise(_c("https://getbailar.com/es/studios/academia-go-salsa/"))
    assert is_noise(_c("https://www.salsavida.com/es/event/chile/santiago-chile/x"))
    assert is_noise(_c("https://servisantiago.org/academia-de-baile/casa-del-mambo/"))
    assert is_noise(_c("https://www.greenparkeventos.cl/centros-de-eventos/jsd-academy"))
    assert is_noise(_c("https://www.portalpuentealto.cl/sabor-latino-chile/"))
    assert is_noise(
        _c("https://izakodanceacademy.com/clases-de-bachata-en-la-florida/")
    )
    # La academia dueña del sitio se conserva por su home.
    assert not is_noise(_c("https://izakodanceacademy.com/"))


def test_filter_noise_returns_kept_and_count():
    from bailoteca.sources.filters import filter_noise

    kept, dropped = filter_noise(
        [
            _c("https://asyouwish.cl/"),
            _c("https://www.superprof.cl/x"),
        ]
    )
    assert [c.url for c in kept] == ["https://asyouwish.cl/"]
    assert dropped == 1
