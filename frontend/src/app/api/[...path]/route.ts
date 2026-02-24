// API Route для проксирования всех /api/* запросов на backend
// Это позволяет избежать CORS при локальной разработке

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://corp.robotail.pro';

export async function GET(request: NextRequest) {
    return proxyRequest(request, 'GET');
}

export async function POST(request: NextRequest) {
    return proxyRequest(request, 'POST');
}

export async function PUT(request: NextRequest) {
    return proxyRequest(request, 'PUT');
}

export async function PATCH(request: NextRequest) {
    return proxyRequest(request, 'PATCH');
}

export async function DELETE(request: NextRequest) {
    return proxyRequest(request, 'DELETE');
}

async function proxyRequest(request: NextRequest, method: string) {
    try {
        // Получаем путь из URL запроса
        const url = new URL(request.url);
        // Убираем /api из начала пути
        const apiPath = url.pathname.replace(/^\/api\//, '');

        // Формируем полный URL к backend
        const backendUrl = `${BACKEND_URL}/api/${apiPath}`;

        // Копируем query параметры
        const searchParams = url.searchParams.toString();
        const fullUrl = searchParams ? `${backendUrl}?${searchParams}` : backendUrl;

        console.log(`[Proxy] ${method} ${fullUrl}`);

        // Копируем заголовки из оригинального запроса
        const headers = new Headers();
        request.headers.forEach((value, key) => {
            // Пропускаем заголовки, которые не нужно передавать
            if (!['host', 'connection', 'content-length'].includes(key.toLowerCase())) {
                headers.set(key, value);
            }
        });

        // Получаем тело запроса как бинарные данные.
        // ВАЖНО: text() ломает бинарные файлы (png/mp4) при multipart/form-data.
        let body: BodyInit | undefined = undefined;
        if (method !== 'GET' && method !== 'HEAD') {
            const rawBody = await request.arrayBuffer();
            body = rawBody.byteLength > 0 ? rawBody : undefined;
        }

        // Делаем запрос к backend
        const response = await fetch(fullUrl, {
            method,
            headers,
            body,
        });

        // Копируем заголовки из ответа backend
        const responseHeaders = new Headers();
        response.headers.forEach((value, key) => {
            responseHeaders.set(key, value);
        });

        // Для 204/205/304 тело ответа запрещено по HTTP-спецификации.
        // Иначе NextResponse выбрасывает: "Invalid response status code 204".
        const noBodyStatuses = new Set([204, 205, 304]);
        if (noBodyStatuses.has(response.status)) {
            responseHeaders.delete('content-length');
            responseHeaders.delete('content-type');

            return new NextResponse(null, {
                status: response.status,
                statusText: response.statusText,
                headers: responseHeaders,
            });
        }

        // response.text() уже декодирует gzip/br/deflate.
        // Удаляем encoding-заголовки, иначе браузер попытается
        // распаковать повторно → ERR_CONTENT_DECODING_FAILED.
        responseHeaders.delete('content-encoding');
        responseHeaders.delete('content-length');
        responseHeaders.delete('transfer-encoding');

        // Возвращаем ответ от backend
        const responseBody = await response.text();

        return new NextResponse(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders,
        });
    } catch (error: any) {
        console.error('[Proxy Error]', error.message);
        return NextResponse.json(
            { error: 'Ошибка при обращении к backend', message: error.message },
            { status: 502 }
        );
    }
}
