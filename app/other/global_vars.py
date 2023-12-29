with open('pain_data.txt') as pd:
    file = [line for line in pd]
    proxy = file[0].strip()
    token_dadata = file[1].strip()
    secret_key_dadata = file[2].strip()