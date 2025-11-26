# Auto-generated Makefile

CC = gcc
CFLAGS = -Wall -Wextra -Iinclude -O2
TARGET = reversed_binary

SRCS = src/utilities_1.c src/utilities_2.c src/utilities_3.c src/utilities_4.c src/utilities_5.c src/utilities_6.c src/utilities_7.c src/utilities_8.c src/utilities_9.c
OBJS = utilities_1.o utilities_2.o utilities_3.o utilities_4.o utilities_5.o utilities_6.o utilities_7.o utilities_8.o utilities_9.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET)

%.o: src/%.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
