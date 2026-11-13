"""Shared tunic settings. The game's native loader applies them on restart."""
DEFAULT_RGB = (80, 160, 75)
RGB_KEYS = ('tunic_red', 'tunic_green', 'tunic_blue')


def rgb(settings):
    result = []
    for key, default in zip(RGB_KEYS, DEFAULT_RGB):
        try:
            value = int(settings.get(key, default))
        except (ValueError, TypeError, OverflowError):
            value = default
        result.append(max(0, min(255, value)))
    return tuple(result)


def hex_color(settings):
    return '#%02X%02X%02X' % rgb(settings)


def from_hex(text):
    text = text.strip().removeprefix('#')
    if len(text) != 6 or any(c not in '0123456789abcdefABCDEF' for c in text):
        raise ValueError('Use six hexadecimal digits, for example #5080FF.')
    return dict(zip(RGB_KEYS, (int(text[i:i + 2], 16) for i in (0, 2, 4)))) | {'custom_tunic_color': 1}
