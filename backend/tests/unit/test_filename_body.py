from kms.ingest.worker import filename_body


def test_filename_body_lists_the_name_then_its_words():
    assert filename_body("notes-lisbon.txt") == "notes-lisbon.txt notes lisbon txt"
    assert filename_body("IMG_2101.jpg") == "IMG_2101.jpg IMG 2101 jpg"
    assert filename_body("café menu.txt") == "café menu.txt café menu txt"
