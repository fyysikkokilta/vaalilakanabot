# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan Discourse-pohjaisella keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi). 

## Ominaisuudet
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus 
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakanaa
- Jauhistelu

## Käyttöönotto
- asenna `python-telegram-bot`-kirjasto (versio >=12) ja muut tarvittavat kirjastot
- lisää Bot Fatherilta saatava `VAALILAKANABOT_TOKEN` ympäristönmuuttujaksi käyttöjärjestelmään.
- täydennä ADMIN_CHAT_ID koodiin (halutun ryhmän id:n saa esimerkiksi lisäämällä botin `@RawDataBot` haluttuun ryhmään)
- Päivitä TOPIC_LIST_URL ja QUESTION_LIST_URL -muuttujat koodiin. Katso [Discoursen dokumentaatio](https://docs.discourse.org/#tag/Categories/paths/~1c~1{id}.json/get) oikeanlaisen URL:n asettamiseksi.
- `$ python vaalilakanabot2019.py` 
- lisää botti relevantteihin keskusteluryhmiin

## Running the bot with Docker
- create copies of the example_*.json files with such names that the "example_" part is removed.
- create `bot.env` where `VAALILAKANABOT_TOKEN` and `ADMIN_CHAT_ID` env variables are stored
- Update TOPIC_LIST_URL ja QUESTION_LIST_URL -variables in the code. See [Discourse documentation](https://docs.discourse.org/#tag/Categories/paths/~1c~1{id}.json/get) for formatting.
- ```bash
  # Use this to run the development container (from dev branch in GitHub) 
  docker-compose -f docker-compose.yml --profile dev up -d
  
  # Use this to run the production container (from master branch in GitHub) 
  docker-compose -f docker-compose.yml --profile prod up -d
    ```

## Komennot
Botti tukee seuraavia komentoja:
- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/jauhis` Näytää vaaliaiheisen kuvan.
- `/lakana` Näytää vaalien ehdokastilanteen.

Admin-chatissa seuraavat komennot ovat käytössä:
- `/lisaa` Lisää ehdokkaan vaalilakanaan.
- `/lisaa_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/poista` Poistaa ehdokkaan lakanasta.
- `/valittu` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan.
- `/tiedota` Julkaisee uuden merkinnän vaalilakanassa.

## Lisätietoa
Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf). 

Botin tekivät [Einari Tuukkanen](https://github.com/EinariTuukkanen) ja Uula Ollila.
