#include <winsock2.h>
#include <iphlpapi.h>
#include <stdio.h>
#include <windows.h>

struct ScanResult {
    char *ipAdress;
    DWORD resultCode;
    ULONG resultAddress[2];
};

struct ThreadData {
    char *address;
    struct ScanResult *result;
};

DWORD WINAPI scan(LPVOID args) {
    struct ThreadData *data = (struct ThreadData *)args;

    IPAddr destIp = inet_addr(data->address);
    IPAddr srcIp = 0;
    data->result->ipAdress = data->address;
    ULONG PhysAddrLen = 6;

    data->result->resultCode = SendARP(destIp, srcIp, data->result->resultAddress, &PhysAddrLen);
    
    return 0;
}

struct ScanResult* scanAll(char ** addresses, size_t count) {
    struct ScanResult *results = malloc(count * sizeof(struct ScanResult));
    memset(results, 0x0, count * sizeof(struct ScanResult));
    HANDLE *threads = malloc(count * sizeof(HANDLE));
    struct ThreadData *threadData = malloc(count * sizeof(struct ThreadData));

    for (int i = 0; i < count; i++) {
        threadData[i].address = addresses[i];
        threadData[i].result = &results[i];

        threads[i] = CreateThread(
            NULL,
            0,
            scan,
            &threadData[i],
            0,
            NULL
        );

        if (threads[i] == NULL) {
            fprintf(stderr, "<ARP> Failed to create scan thread for %s", addresses[i]);
        }
    }

    for (size_t i = 0; i < count; i++) {
        if (threads[i] != NULL) {
            WaitForSingleObject(threads[i], INFINITE);
            CloseHandle(threads[i]);
        }
    }

    free(threads);
    free(threadData);

    return results;
}
