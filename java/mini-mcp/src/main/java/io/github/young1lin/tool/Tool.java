package io.github.young1lin.tool;

import java.lang.reflect.Method;
import java.util.Map;

public interface Tool {

    String getName();

    Map<String, Class<?>> getArguments();

    Method getFunc();

    Object getInstance();

    java.util.List<String> getRequiredArguments();

    default String getDescription() {
        return "";
    }

}
