# report-server

schedule reports to be sent automatically via email

- How to (TBA)

1. build

```
$ docker build -t report .
$ docker run -p 5656:5656 -e TZ=Asia/Tokyo -it report:latest
```

2. auth

```
in browser ... localhost:5656/auth
```

3. hello, goodbye

```
$ curl 0.0.0.0:5656/hello -X POST -H "Content-Type: application/json" --data '{"comment": "特記事項: 本日8時から勤務"}'
$ curl 0.0.0.0:5656/goodbye -X POST -H "Content-Type: application/json" --data '{"comment": "特記事項: 明日は8時から勤務"}'
```
