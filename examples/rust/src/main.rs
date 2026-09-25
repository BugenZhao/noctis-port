//! Noctis semantic preview: parameters, fields, lifetimes and control flow.

const DEFAULT_LIMIT: usize = 12;
static LABEL: &str = "Noctis";

#[derive(Debug, Clone)]
struct Record<'a, T> {
    label: &'a str,
    value: T,
}

trait Describe {
    fn describe(&self) -> String;
}

impl<'a> Describe for Record<'a, usize> {
    fn describe(&self) -> String {
        format!("{}: {}", self.label, self.value)
    }
}

impl<'a, T> Record<'a, T> {
    fn new(label: &'a str, value: T) -> Self {
        Self { label, value }
    }

    fn replace(&mut self, value: T) {
        self.value = value;
    }
}

enum Status {
    Ready,
    Pending(usize),
}

macro_rules! record {
    ($value:expr) => {
        Record::new(LABEL, $value)
    };
}

fn choose<'a>(items: &'a [Record<'a, usize>], limit: usize) -> Option<&'a str> {
    for item in items {
        if item.value < limit {
            return Some(item.label);
        }
    }
    None
}

fn main() {
    let mut item = record!(DEFAULT_LIMIT);
    item.replace(8);
    let status = Status::Pending(item.value);
    let ready = Status::Ready;
    let value = match status {
        Status::Ready => 0,
        Status::Pending(count) => count,
    };
    let values = [item];
    let selected = choose(&values, DEFAULT_LIMIT).unwrap_or("empty");
    println!("{selected}: {value} / {}", values[0].describe());
    let _ = ready;
}
