s = "hello world"
n = 0
vowels = "aeiou"
i = 0
while i < len(s):
    c = s[i]
    if c in vowels:
        n = n + 1
    i = i + 1
print(n)
