# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan Discourse-pohjaisella keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi). 

## Ominaisuudet
- Kiltalaiset voivat hakea sekä vaaleilla valittaviin että ei-vaaleilla valittaviin virkoihin.
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus.
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakanaa.
- Jauhistelu

## Käyttöönotto
- asenna `python-telegram-bot`-kirjasto (versio >=21) ja muut tarvittavat kirjastot.
- lisää Telegram-bot Bot Father -botilla ja ota botin token talteen.
- Luo Discourse api-avain bottia varten.
- Luo admin Telegram-ryhmä ja ota sen id talteen esimerkiksi botilla `@RawDataBot`.
- Luo vaalilakana Fiirumille.
    - Viestissä, jossa vaalilakana sijaitsee ei saa olla muuta tekstiä kuin itse vaalilakana.
    - Jaoksien nimet tulee olla ISOLLA kirjoitettuna ja rivi saa sisältää vain suomenkielisen ja englanninkielisen käännöksen /-merkillä jaettuna.
    - Roolirivit tulee olla muodossa `{suomenkielinen nimi} / {englanninkielinen nimi} ({valittavien määrä}) {haun deadline (muodossa xx.yy.}`
        - Kaikki muut paitsi suomenkielinen nimi ovat vapaaehtoisia, mutta järjestyksen tulee olla juuri tämä.
- Luo `bot.env` esimerkkitiedoston `bot.env.example` mukaisesti.
- `$ python vaalilakanabot.py` 
- lisää botti relevantteihin keskusteluryhmiin.

## Running the bot with Docker
- Create a Telegram bot and save the bot token.
- Create Discourse api keys to be used by the bot.
- Create an admin Telegram group and get the id of the group using, for example, `@RawDataBot`.
- Create the vaalilakana for Fiirumi.  
    - The message containing the vaalilakana must not have any text other than the vaalilakana itself.  
    - Division names must be written in ALL CAPS, and each line should contain only the Finnish and English translations separated by a `/`.  
    - Role lines must follow the format:  
      `{Finnish name} / {English name} ({number of positions}) {application deadline (in the format xx.yy.)}`  
        - Everything except the Finnish name is optional, but the order must be exactly as specified.
- Create `bot.env` according to the example file `bot.env.example`.
- Make sure the empty vaalilakana is already created when starting the bot so that the local json is populated.
- Start the bot using provided `update-deployment.sh` script.

## Komennot
Botti tukee seuraavia komentoja:
- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/lakana` Näyttää vaalien ehdokastilanteen.
- `/jauhis` Näyttää vaaliaiheisen kuvan.
- `/jauh` Näyttää vaaliaiheisen kuvan.
- `/jauho` Näyttää vaaliaiheisen kuvan.
- `/lauh` Näyttää vaaliaiheisen kuvan.
- `/mauh` Näyttää vaaliaiheisen kuvan.
- `/hae` Aloittaa hakemuslomakkeen täyttämisen.

Admin-chatissa seuraavat komennot ovat käytössä:
- `/poista` Poistaa ehdokkaan lakanasta. (toimii myös ei-vaaleilla valittavaan virkoihin; hakijan voi siis poistaa botin kautta)
- `/lisaa_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/poista_fiirumi` Poistaa vaalilakanaan lisätyn fiirumipostauksen.
- `/valittu` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan. (toimii myös ei-vaaleilla valittavaan virkoihin)
- `/muokkaa_roolia` Lisää uuden roolin tai muokkaa olevassa olevaa roolia vaalilakanassa.
- `/poista_rooli` Poistaa roolin vaalilakanasta.
- `/vie_tiedot` Luo hakijoiden tiedoista CSV-tiedoston.

## Lisätietoa
Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf). 

Botin tekivät [Einari Tuukkanen](https://github.com/EinariTuukkanen) ja Uula Ollila.
