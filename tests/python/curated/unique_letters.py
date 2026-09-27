s = "banana"
seen = ""
i = 0
while i < len(s):
    c = s[i]
    if c in seen:
        pass
    else:
        seen = seen + c
    i = i + 1
print(seen)
