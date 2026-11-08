package com.ainvest.marketdata;

import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

// a tiny local HTTP server that plays the FX provider in tests: each test scripts the answers
// (status, body, delay) and afterwards checks how many times the service really called it
public final class FakeFxProvider {

    public record Answer(int status, String body, long delayMillis) {
    }

    public static final String USD_TRY_JSON =
            "{\"amount\":1.0,\"base\":\"USD\",\"date\":\"2026-11-06\",\"rates\":{\"TRY\":50.153}}";

    private final HttpServer server;
    private final Queue<Answer> script = new ConcurrentLinkedQueue<>();
    private final AtomicInteger hits = new AtomicInteger();
    private volatile Answer whenScriptIsEmpty = ok();

    public FakeFxProvider() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/latest", exchange -> {
            hits.incrementAndGet();
            Answer answer = script.poll();
            if (answer == null) {
                answer = whenScriptIsEmpty;
            }
            try {
                if (answer.delayMillis() > 0) {
                    Thread.sleep(answer.delayMillis());
                }
                byte[] bytes = answer.body().getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(answer.status(), bytes.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(bytes);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (IOException ignored) {
                // the client already gave up (timeout test) - nothing to do
            } finally {
                exchange.close();
            }
        });
        // several threads, so a slow answer does not block the next request
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();
    }

    public static Answer ok() {
        return new Answer(200, USD_TRY_JSON, 0);
    }

    public static Answer status(int status) {
        return new Answer(status, "{\"message\":\"fake error\"}", 0);
    }

    public static Answer slow(long delayMillis) {
        return new Answer(200, USD_TRY_JSON, delayMillis);
    }

    public String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    public void reset() {
        script.clear();
        hits.set(0);
        whenScriptIsEmpty = ok();
    }

    public void then(Answer... answers) {
        script.addAll(java.util.List.of(answers));
    }

    public void always(Answer answer) {
        whenScriptIsEmpty = answer;
    }

    public int hits() {
        return hits.get();
    }

    public void stop() {
        server.stop(0);
    }
}
