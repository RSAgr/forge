FROM postgis/postgis:16-3.4

COPY --from=postgres:16 /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
