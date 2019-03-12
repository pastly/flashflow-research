from nacl.exceptions import CryptoError


def try_decrypt(box, cypher):
    '''
    Try to decrypt **cypher** using **box**. If we can\'t, return None.
    '''
    try:
        return box.decrypt(cypher)
    except CryptoError:
        return None


def find_correct_box(boxes, cypher):
    '''
    Try decrypting **cypher** with each box in **boxes** until one works.
    Return the working box and the plaintext. If we can't find a working box,
    return None, None
    '''
    for box in boxes:
        plain = try_decrypt(box, cypher)
        if plain is not None:
            return box, plain
    return None, None
