/* Dewiar.app/Contents/MacOS/Dewiar — пускач приложения для Mac (собирает tools/build_mac.sh: clang -framework Cocoa).

   Запускает интерфейс ui/app.py своим Python из Contents/Resources/python отдельным процессом и живёт, пока живёт он.
   Почему не exec: macOS спрашивает разрешение на микрофон и запись экрана от имени «ответственного» процесса — это сам
   пускач (Mach-O из Contents/MacOS, его Info.plist с NSMicrophoneUsageDescription). Python, интерфейс и ядро — его
   потомки, поэтому окно разрешения говорит «Dewiar», а не «python3». У пускача LSUIElement — своего значка в Доке у него
   нет; значок и окна — у интерфейса (процесс называется «Dewiar»: копия python3 под этим именем, см. build_mac.sh).

   Пускач — маленькое приложение Cocoa, чтобы слышать macOS: Dewiar открыли ещё раз (Launchpad, Finder, Spotlight) —
   «покажись»; ссылка dewiar://… или файл .dewiar — «открой». Это он пишет строкой в ~/Library/Caches/Dewiar/
   launcher.signal, интерфейс читает (ui/macui.py, main_mac). Выход из системы — завершает интерфейс.

   Внутри приложения ничего не пишется (подпись бы сломалась): кэш байт-кода — в ~/Library/Caches/Dewiar/pycache. */
#import <Cocoa/Cocoa.h>
#include <mach-o/dyld.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>

extern char **environ;
static pid_t child = 0;
static dispatch_source_t watcher;

static void forward(int sig) {
    if (child > 0) kill(child, sig);
}

static void poke(NSString *line) {
    NSString *dir = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Caches/Dewiar"];
    [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *f = [dir stringByAppendingPathComponent:@"launcher.signal"];
    NSString *old = [NSString stringWithContentsOfFile:f encoding:NSUTF8StringEncoding error:nil] ?: @"";
    NSString *text = [old stringByAppendingFormat:@"%@\n", line];
    [text writeToFile:f atomically:YES encoding:NSUTF8StringEncoding error:nil];
}

@interface DewiarLauncher : NSObject <NSApplicationDelegate>
@end

@implementation DewiarLauncher
- (void)applicationDidFinishLaunching:(NSNotification *)note {
    NSString *contents = [[[NSBundle mainBundle] bundlePath] stringByAppendingPathComponent:@"Contents"];
    NSString *py = [contents stringByAppendingPathComponent:@"Resources/python/bin/Dewiar"];
    if (![[NSFileManager defaultManager] isExecutableFileAtPath:py])      /* копии нет — обычный python3 */
        py = [contents stringByAppendingPathComponent:@"Resources/python/bin/python3"];
    NSString *app = [contents stringByAppendingPathComponent:@"Resources/app/ui/app.py"];

    NSString *cache = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Caches/Dewiar/pycache"];
    setenv("PYTHONPYCACHEPREFIX", cache.fileSystemRepresentation, 1);
    unsetenv("PYTHONHOME");                 /* чужой Python человека не должен подменить наш */
    unsetenv("PYTHONPATH");
    unsetenv("PYTHONSTARTUP");
    setenv("PYTHONNOUSERSITE", "1", 1);
    setenv("DEWIAR_APP_BUNDLE", [[NSBundle mainBundle] bundlePath].fileSystemRepresentation, 1);
    if (!getenv("LANG")) setenv("LANG", "ru_RU.UTF-8", 1);   /* из Finder LANG не приходит */

    NSMutableArray<NSString *> *args = [NSMutableArray arrayWithObjects:py, @"-X", @"utf8", app, nil];
    NSArray<NSString *> *mine = [[NSProcessInfo processInfo] arguments];
    for (NSUInteger i = 1; i < mine.count; i++) {
        if ([mine[i] hasPrefix:@"-psn_"]) continue;              /* старые macOS добавляют номер процесса */
        [args addObject:mine[i]];
    }
    char **argv = calloc(args.count + 1, sizeof(char *));
    for (NSUInteger i = 0; i < args.count; i++) argv[i] = strdup(args[i].fileSystemRepresentation);
    int rc = posix_spawn(&child, argv[0], NULL, NULL, argv, environ);
    if (rc != 0) {
        NSAlert *a = [NSAlert new];
        a.messageText = @"Dewiar не запустился";
        a.informativeText = [NSString stringWithFormat:@"Не запустился Python внутри приложения (%s). Скачайте Dewiar "
                             "с dewiar.pro заново и перетащите в «Программы».", strerror(rc)];
        [a runModal];
        exit(1);
    }
    watcher = dispatch_source_create(DISPATCH_SOURCE_TYPE_PROC, (uintptr_t)child, DISPATCH_PROC_EXIT, dispatch_get_main_queue());
    dispatch_source_set_event_handler(watcher, ^{
        int st = 0;
        waitpid(child, &st, 0);
        exit(WIFEXITED(st) ? WEXITSTATUS(st) : 1);
    });
    dispatch_resume(watcher);
}

/* открыли ещё раз, пока работаем (Launchpad, Finder, Spotlight, значок в Доке) — показать виджет */
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    poke(@"hud");
    return NO;
}

/* dewiar://connect?… или файл настроек .dewiar */
- (void)application:(NSApplication *)application openURLs:(NSArray<NSURL *> *)urls {
    for (NSURL *u in urls) poke([@"open " stringByAppendingString:(u.isFileURL ? u.path : u.absoluteString)]);
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    forward(SIGTERM);
    return NSTerminateNow;
}
@end

int main(int argc, const char **argv) {
    @autoreleasepool {
        signal(SIGTERM, forward);
        signal(SIGINT, forward);
        signal(SIGHUP, forward);
        NSApplication *app = [NSApplication sharedApplication];
        DewiarLauncher *d = [DewiarLauncher new];
        app.delegate = d;
        [app run];
    }
    return 0;
}
