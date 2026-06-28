"""BitaHub密码加密模块 - Raw RSA加密."""

# RSA公钥参数（从BitaHub前端JS提取）
RSA_E = 65537  # 0x10001
RSA_N = int(
    "a5aeb8c636ef1fda5a7a17a2819e51e1ea6e0cceb24b95574"
    "ae026536243524f322807df2531a42139389674545f4c596db"
    "162f6e6bbb26498baab074c036777",
    16,
)

# 加密参数
CHUNK_SIZE = 62  # 每个RSA加密块的大小（字节）
DIGIT_BASE = 65536  # A = 2^16（每个digit的基数）


def encrypt_password(password: str) -> str:
    """
    BitaHub 密码加密.

    加密过程（与前端JS一致）:
    1. 密码 -> charCode数组
    2. 补0到CHUNK_SIZE(62)字节的倍数
    3. 每2字节组成一个16位digit（little-endian）
    4. 构建大整数 m
    5. RSA加密: c = m^e mod n
    6. 转换为hex字符串

    Args:
        password: 明文密码

    Returns:
        RSA加密后的hex字符串
    """
    # 步骤1: 转换为charCode数组
    codes = [ord(c) for c in password]

    # 步骤2: 补0到chunkSize的倍数
    while len(codes) % CHUNK_SIZE != 0:
        codes.append(0)

    # 步骤3-4: 每2字节组成digit，构建大整数
    m = 0
    digit_idx = 0
    for i in range(0, len(codes), 2):
        # 每2字节组成一个digit (little-endian: d = b[i] + b[i+1]*256)
        digit_value = codes[i] + (codes[i + 1] << 8) if i + 1 < len(codes) else codes[i]
        m += digit_value * (DIGIT_BASE ** digit_idx)
        digit_idx += 1

    # 步骤5: RSA加密 c = m^e mod n
    c = pow(m, RSA_E, RSA_N)

    # 步骤6: 转换为hex
    return format(c, "x")
