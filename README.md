# MusicFinderBot V16 FULL FIXED

## Tuzatilgan

- Windows `WinError 5 / Отказано в доступе`
- Har yuklash uchun alohida vaqtinchalik papka
- Eski MP3 nomlari bilan to'qnashuv yo'q
- Vaqtinchalik papkalar to'liq avtomatik o'chadi
- `cookies.txt` avtomatik ishlatiladi
- `/round` va `/raund` ikkalasi ishlaydi
- Reply orqali yoki komandadan keyin video yuborish ishlaydi
- Video/animation/video-note/video document qabul qiladi
- FFmpeg topilmasa `imageio-ffmpeg` fallback ishlaydi

## O'rnatish

1. Eski papkadagi `.env` faylni yangi papkaga ko'chiring.
2. Eski papkadagi to'g'ri `cookies.txt` faylni yangi papkaga ko'chiring.
3. Eski botni `Ctrl+C` bilan to'xtating.
4. `UPDATE_AND_RUN.bat` ni oching.

## Round

Videoga reply qilib:

```
/round
```

yoki:

```
/raund
```

Yoki avval `/round` yuborib, keyin videoni yuboring.

## V18 Telegram Mini App

Mini App imkoniyatlari:

- premium mobil dizayn;
- Telegram profil;
- YouTube + Spotify + lokal kutubxona qidiruvi;
- sevimlilar;
- tarix;
- kutubxona va qidiruv statistikasi.

### Mini App URL sozlash

Hosting bergan HTTPS domenni `.env` ichiga yozing:

```env
MINI_APP_URL=https://SIZNING-DOMENINGIZ
WEB_HOST=0.0.0.0
PORT=8080
```

Botni qayta ishga tushirgach `/start` menyusida `✨ Music Mini App` tugmasi chiqadi.

BotFather orqali doimiy Menu Button qo‘yish uchun:

1. `@BotFather` → `/mybots`
2. botni tanlang → `Bot Settings`
3. `Menu Button` → `Configure menu button`
4. hostingdagi `MINI_APP_URL` manzilini kiriting.
<<<<<<< HEAD


## V19 Admin Mini App
- Admin tab faqat `ADMIN_IDS` dagi Telegram ID uchun ko‘rinadi.
- `/adminapp` — admin panelni Telegram ichida ochadi.
- Jami userlar, bugungi yangi userlar, 24 soat/7 kun faollar, qidiruvlar, harakatlar, sevimlilar va kutubxona statistikasi.
- Oxirgi 100 foydalanuvchi, top qidiruvlar va oxirgi faoliyat.
- Yangi user `/start` bosganda yoki Mini Appni ochganda avtomatik ro‘yxatga tushadi.
=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
