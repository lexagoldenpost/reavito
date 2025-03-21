import chardet

with open('requirements.txt', 'rb') as f:
  result = chardet.detect(f.read())

print(result['encoding'])