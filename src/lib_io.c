#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>

#ifdef _WIN32
  #include <windows.h>
  #define EXPORT __declspec(dllexport)
#else
  #include <unistd.h>
  #include <time.h>
  #include <pthread.h>
  #define EXPORT __attribute__((visibility("default")))
#endif

/* =========================================================
 *  HIGH-PRECISION TIMER
 * ========================================================= */
EXPORT double get_time(void) {
#ifdef _WIN32
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (double)count.QuadPart / (double)freq.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
#endif
}

/* =========================================================
 *  PARALLEL FOR (pthread or Windows threads)
 *  Splits loop iterations [0, n) across `num_threads` workers.
 *  work_fn(idx, arg) is called for each index.
 * ========================================================= */
typedef void (*loop_fn)(int idx, void* arg);

typedef struct {
    int start, end;
    loop_fn work;
    void* arg;
} thread_job_t;

#ifdef _WIN32
static DWORD WINAPI thread_worker(LPVOID ptr) {
    thread_job_t* job = (thread_job_t*)ptr;
    for (int i = job->start; i < job->end; i++)
        job->work(i, job->arg);
    return 0;
}
#else
static void* thread_worker(void* ptr) {
    thread_job_t* job = (thread_job_t*)ptr;
    for (int i = job->start; i < job->end; i++)
        job->work(i, job->arg);
    return NULL;
}
#endif

EXPORT void parallel_for(int n, int num_threads, loop_fn work, void* arg) {
    if (num_threads < 1) num_threads = 1;
    if (num_threads > n) num_threads = n;

    thread_job_t* jobs = (thread_job_t*)malloc(num_threads * sizeof(thread_job_t));

#ifdef _WIN32
    HANDLE* handles = (HANDLE*)malloc(num_threads * sizeof(HANDLE));
#else
    pthread_t* threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
#endif

    int chunk = n / num_threads;
    int rem = n % num_threads;
    int start = 0;

    for (int t = 0; t < num_threads; t++) {
        int cnt = chunk + (t < rem ? 1 : 0);
        jobs[t].start = start;
        jobs[t].end = start + cnt;
        jobs[t].work = work;
        jobs[t].arg = arg;

#ifdef _WIN32
        handles[t] = CreateThread(NULL, 0, thread_worker, &jobs[t], 0, NULL);
#else
        pthread_create(&threads[t], NULL, thread_worker, &jobs[t]);
#endif
        start += cnt;
    }

    for (int t = 0; t < num_threads; t++) {
#ifdef _WIN32
        WaitForSingleObject(handles[t], INFINITE);
        CloseHandle(handles[t]);
#else
        pthread_join(threads[t], NULL);
#endif
    }

    free(jobs);
#ifdef _WIN32
    free(handles);
#else
    free(threads);
#endif
}

/* =========================================================
 *  FAST CSV LOADER  (fread + strtod)
 * ========================================================= */
EXPORT double* load_csv_native(char* filename, int num_values) {
    double* memory = (double*)malloc(num_values * sizeof(double));
    if (memory == NULL) {
        printf("Error: malloc(%d bytes) for CSV failed\n", (int)(num_values * sizeof(double)));
        return NULL;
    }

    FILE* file = fopen(filename, "rb");
    if (file == NULL) {
        printf("Error: Cannot open '%s' — %s\n", filename, strerror(errno));
        free(memory);
        return NULL;
    }

    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    if (file_size <= 0) {
        printf("Error: '%s' is empty\n", filename);
        fclose(file);
        free(memory);
        return NULL;
    }

    char* buffer = (char*)malloc(file_size + 1);
    if (buffer == NULL) {
        fclose(file);
        free(memory);
        return NULL;
    }

    size_t bytes_read = fread(buffer, 1, file_size, file);
    fclose(file);
    buffer[bytes_read] = '\0';

    if ((long)bytes_read != file_size) {
        printf("Error: Read %zu of %ld bytes from '%s'\n", bytes_read, file_size, filename);
        free(buffer);
        free(memory);
        return NULL;
    }

    int count = 0;
    char* cursor = buffer;
    char* endptr = NULL;

    while (*cursor != '\0' && count < num_values) {
        while (*cursor != '\0' && isspace((unsigned char)*cursor))
            cursor++;
        if (*cursor == '\0')
            break;

        memory[count] = strtod(cursor, &endptr);
        if (endptr == cursor) {
            endptr = cursor + 1;
        }
        count++;
        cursor = endptr;

        while (*cursor != '\0' && (*cursor == ',' || isspace((unsigned char)*cursor)))
            cursor++;
    }

    free(buffer);

    if (count < num_values) {
        memset(memory + count, 0, (num_values - count) * sizeof(double));
        printf("Warning: '%s' has %d values (expected %d)\n", filename, count, num_values);
    }

    return memory;
}
