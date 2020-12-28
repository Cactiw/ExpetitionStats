

digit_to_emoji = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟"  # just because it exists
}


def translate_number_to_emoji(n: int) -> str:
    res = ""
    while n > 0:
        digit = n % 10
        res += digit_to_emoji.get(digit, "")
        n /= 10
    return res
