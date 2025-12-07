package io.github.young1lin.util;

import java.util.logging.Formatter;
import java.util.logging.LogRecord;

/**
 * 自定义日志格式化器，支持显示线程ID
 */
public class ThreadAwareFormatter extends Formatter {

    @Override
    public String format(LogRecord record) {
        StringBuilder sb = new StringBuilder();

        // 日期时间
        sb.append(String.format("%1$tY-%1$tm-%1$td %1$tH:%1$tM:%1$tS", record.getMillis()));

        // 日志级别（使用英文，避免中文显示问题）
        String level = record.getLevel().getName();
        sb.append(" [").append(level).append("]");

        // 线程信息（支持虚拟线程）
        Thread currentThread = Thread.currentThread();
        long threadId = currentThread.threadId();
        String threadName = currentThread.getName();
        boolean isVirtual = currentThread.isVirtual();

        // 构建线程标识：优先使用线程名称，如果是虚拟线程则标注
        if (isVirtual) {
            // 虚拟线程：显示名称和ID（虚拟线程的ID可能重复使用）
            sb.append(" [V-").append(threadName).append("-").append(threadId).append("]");
        } else {
            // 平台线程：显示ID，如果名称不是默认的则也显示名称
            if (threadName.startsWith("Thread-") && threadName.equals("Thread-" + threadId)) {
                // 默认名称，只显示ID
                sb.append(" [T-").append(threadId).append("]");
            } else {
                // 自定义名称，显示名称和ID
                sb.append(" [T-").append(threadName).append("-").append(threadId).append("]");
            }
        }

        // 类名和方法名（显示全限定名）
        String sourceClassName = record.getSourceClassName();
        String sourceMethodName = record.getSourceMethodName();
        if (sourceClassName != null) {
            // 显示全限定类名
            sb.append(" ").append(sourceClassName);
            if (sourceMethodName != null) {
                sb.append(".").append(sourceMethodName);
            }
        }

        sb.append(" - ");

        // 日志消息
        sb.append(formatMessage(record));

        // 异常信息
        if (record.getThrown() != null) {
            sb.append("\n");
            java.io.StringWriter sw = new java.io.StringWriter();
            java.io.PrintWriter pw = new java.io.PrintWriter(sw);
            record.getThrown().printStackTrace(pw);
            sb.append(sw.toString());
        }

        sb.append("\n");
        return sb.toString();
    }
}

